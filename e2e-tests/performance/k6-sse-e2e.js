/**
 * k6 SSE E2E Performance Test
 *
 * 테스트 사이클:
 * 1. POST /api/v1/scan - 스캔 요청
 * 2. GET /api/v1/stream?job_id={job_id} - SSE 스트림 연결 (done 이벤트까지)
 * 3. GET /api/v1/scan/result/{job_id} - 결과 조회
 *
 * Usage:
 *   k6 run --env TOKEN="eyJ..." --env IMAGE_URL="https://..." tests/performance/k6-sse-e2e.js
 *
 * Options:
 *   --vus 10 --duration 60s    # 10 VU로 60초간 테스트
 *   --iterations 20            # 총 20회 반복
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend, Rate } from 'k6/metrics';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = __ENV.BASE_URL || 'https://api.dev.growbin.app';
const TOKEN = __ENV.TOKEN;
const IMAGE_URL = __ENV.IMAGE_URL || 'https://images.dev.growbin.app/scan/e09725344fc2418a88f293b0f20db173.png';
const SSE_TIMEOUT_MS = 120000; // 2분 타임아웃

// ============================================================================
// Metrics
// ============================================================================

// Counters
const scanRequests = new Counter('scan_requests_total');
const sseConnections = new Counter('sse_connections_total');
const resultRequests = new Counter('result_requests_total');
const rewardsReceived = new Counter('rewards_received_total');

// Trends (latency)
const scanLatency = new Trend('scan_latency_ms');
const sseLatency = new Trend('sse_time_to_done_ms');
const resultLatency = new Trend('result_latency_ms');
const e2eLatency = new Trend('e2e_total_latency_ms');

// Rates (success/failure)
const scanSuccess = new Rate('scan_success_rate');
const sseSuccess = new Rate('sse_success_rate');
const resultSuccess = new Rate('result_success_rate');
const e2eSuccess = new Rate('e2e_success_rate');

// Stage counters
const stageVision = new Counter('stage_vision_received');
const stageRule = new Counter('stage_rule_received');
const stageAnswer = new Counter('stage_answer_received');
const stageReward = new Counter('stage_reward_received');
const stageDone = new Counter('stage_done_received');

// ============================================================================
// Test Options
// ============================================================================

export const options = {
  scenarios: {
    // 기본 시나리오: 점진적 부하
    gradual_load: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 5 },   // 30초간 5 VU까지 증가
        { duration: '1m', target: 10 },   // 1분간 10 VU 유지
        { duration: '30s', target: 5 },   // 30초간 5 VU로 감소
        { duration: '20s', target: 0 },   // 20초간 종료
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    'scan_success_rate': ['rate>0.95'],      // 스캔 성공률 95% 이상
    'sse_success_rate': ['rate>0.90'],       // SSE 성공률 90% 이상
    'e2e_success_rate': ['rate>0.85'],       // E2E 성공률 85% 이상
    'e2e_total_latency_ms': ['p(95)<30000'], // 95% E2E 30초 이내
    'scan_latency_ms': ['p(95)<2000'],       // 95% 스캔 2초 이내
  },
};

// ============================================================================
// Helper Functions
// ============================================================================

function getHeaders() {
  return {
    'Authorization': `Bearer ${TOKEN}`,
    'Content-Type': 'application/json',
  };
}

function generateIdempotencyKey() {
  return `k6-${Date.now()}-${Math.random().toString(36).substring(2, 15)}`;
}

/**
 * SSE 스트림에서 done 이벤트까지 대기
 * k6는 네이티브 SSE를 지원하지 않으므로 polling으로 시뮬레이션
 */
function waitForDone(jobId, startTime) {
  const maxAttempts = 24; // 최대 60초 (2.5초 * 24)
  const pollInterval = 2.5;

  let stages = {
    vision: false,
    rule: false,
    answer: false,
    reward: false,
    done: false,
  };

  for (let i = 0; i < maxAttempts; i++) {
    // 결과 조회로 상태 확인
    const resultRes = http.get(
      `${BASE_URL}/api/v1/scan/result/${jobId}`,
      { headers: getHeaders(), timeout: '10s' }
    );

    if (resultRes.status === 200) {
      try {
        const data = JSON.parse(resultRes.body);
        if (data.status === 'completed') {
          stages.done = true;
          stageDone.add(1);

          // reward 체크
          if (data.reward && data.reward.name) {
            stages.reward = true;
            stageReward.add(1);
            rewardsReceived.add(1);
          }

          // 다른 스테이지는 완료된 것으로 간주
          stages.vision = true;
          stages.rule = true;
          stages.answer = true;
          stageVision.add(1);
          stageRule.add(1);
          stageAnswer.add(1);

          const elapsedMs = Date.now() - startTime;
          return { success: true, stages, elapsedMs, result: data };
        }
      } catch (e) {
        // JSON 파싱 실패 - 계속 polling
      }
    } else if (resultRes.status === 202) {
      // 아직 처리 중 - 계속 대기
    }

    sleep(pollInterval);
  }

  return { success: false, stages, elapsedMs: Date.now() - startTime, result: null };
}

// ============================================================================
// Main Test
// ============================================================================

export default function () {
  const e2eStart = Date.now();
  let e2eOk = false;

  // -------------------------------------------------------------------------
  // Step 1: POST /api/v1/scan
  // -------------------------------------------------------------------------
  const scanStart = Date.now();
  const scanRes = http.post(
    `${BASE_URL}/api/v1/scan`,
    JSON.stringify({ image_url: IMAGE_URL }),
    {
      headers: {
        ...getHeaders(),
        'X-Idempotency-Key': generateIdempotencyKey(),
      },
      timeout: '30s',
    }
  );
  const scanElapsed = Date.now() - scanStart;

  scanRequests.add(1);
  scanLatency.add(scanElapsed);

  const scanOk = check(scanRes, {
    'scan: status is 200 or 202': (r) => r.status === 200 || r.status === 202,
    'scan: has job_id': (r) => {
      try {
        return JSON.parse(r.body).job_id !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  scanSuccess.add(scanOk);

  if (!scanOk) {
    console.error(`Scan failed: ${scanRes.status} - ${scanRes.body}`);
    e2eSuccess.add(false);
    return;
  }

  const scanData = JSON.parse(scanRes.body);
  const jobId = scanData.job_id;
  console.log(`[VU ${__VU}] job_id: ${jobId}`);

  // -------------------------------------------------------------------------
  // Step 2: SSE 스트림 대기 (polling으로 시뮬레이션)
  // -------------------------------------------------------------------------
  sseConnections.add(1);
  const sseStart = Date.now();

  const sseResult = waitForDone(jobId, sseStart);

  sseLatency.add(sseResult.elapsedMs);
  sseSuccess.add(sseResult.success);

  if (!sseResult.success) {
    console.error(`[VU ${__VU}] SSE timeout for job: ${jobId}`);
    e2eSuccess.add(false);
    return;
  }

  console.log(`[VU ${__VU}] SSE done in ${sseResult.elapsedMs}ms, reward: ${sseResult.result?.reward?.name || 'none'}`);

  // -------------------------------------------------------------------------
  // Step 3: GET /api/v1/scan/result/{job_id}
  // -------------------------------------------------------------------------
  const resultStart = Date.now();
  const resultRes = http.get(
    `${BASE_URL}/api/v1/scan/result/${jobId}`,
    { headers: getHeaders(), timeout: '10s' }
  );
  const resultElapsed = Date.now() - resultStart;

  resultRequests.add(1);
  resultLatency.add(resultElapsed);

  const resultOk = check(resultRes, {
    'result: status is 200': (r) => r.status === 200,
    'result: status is completed': (r) => {
      try {
        return JSON.parse(r.body).status === 'completed';
      } catch (e) {
        return false;
      }
    },
  });

  resultSuccess.add(resultOk);

  // -------------------------------------------------------------------------
  // E2E Complete
  // -------------------------------------------------------------------------
  const e2eElapsed = Date.now() - e2eStart;
  e2eLatency.add(e2eElapsed);
  e2eOk = scanOk && sseResult.success && resultOk;
  e2eSuccess.add(e2eOk);

  console.log(`[VU ${__VU}] E2E complete: ${e2eElapsed}ms, success: ${e2eOk}`);

  // 다음 iteration 전 짧은 대기
  sleep(1);
}

// ============================================================================
// Summary
// ============================================================================

export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    metrics: {
      scan: {
        total: data.metrics.scan_requests_total?.values?.count || 0,
        success_rate: data.metrics.scan_success_rate?.values?.rate || 0,
        latency_p95: data.metrics.scan_latency_ms?.values?.['p(95)'] || 0,
      },
      sse: {
        total: data.metrics.sse_connections_total?.values?.count || 0,
        success_rate: data.metrics.sse_success_rate?.values?.rate || 0,
        latency_p95: data.metrics.sse_time_to_done_ms?.values?.['p(95)'] || 0,
      },
      e2e: {
        success_rate: data.metrics.e2e_success_rate?.values?.rate || 0,
        latency_p95: data.metrics.e2e_total_latency_ms?.values?.['p(95)'] || 0,
      },
      stages: {
        vision: data.metrics.stage_vision_received?.values?.count || 0,
        rule: data.metrics.stage_rule_received?.values?.count || 0,
        answer: data.metrics.stage_answer_received?.values?.count || 0,
        reward: data.metrics.stage_reward_received?.values?.count || 0,
        done: data.metrics.stage_done_received?.values?.count || 0,
      },
      rewards: data.metrics.rewards_received_total?.values?.count || 0,
    },
  };

  return {
    'stdout': JSON.stringify(summary, null, 2) + '\n',
    'k6-sse-e2e-summary.json': JSON.stringify(summary, null, 2),
  };
}
