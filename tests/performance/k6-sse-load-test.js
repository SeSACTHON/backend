/**
 * k6 SSE Load Test - VU 50 부하테스트
 *
 * 테스트 시나리오:
 * 1. POST /api/v1/scan - 스캔 요청
 * 2. Polling으로 결과 대기 (done까지)
 * 3. 최종 결과 확인
 *
 * Usage:
 *   # VU 50으로 2분간 테스트
 *   k6 run --env TOKEN="eyJ..." tests/performance/k6-sse-load-test.js
 *
 *   # VU 수 조정
 *   k6 run --env TOKEN="eyJ..." --env VUS=100 tests/performance/k6-sse-load-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend, Rate, Gauge } from 'k6/metrics';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = __ENV.BASE_URL || 'https://api.dev.growbin.app';
const TOKEN = __ENV.TOKEN;
const IMAGE_URL = __ENV.IMAGE_URL || 'https://images.dev.growbin.app/scan/e09725344fc2418a88f293b0f20db173.png';
const TARGET_VUS = parseInt(__ENV.VUS) || 50;
const TEST_DURATION = __ENV.DURATION || '2m';

// ============================================================================
// Metrics
// ============================================================================

// Counters
const scanRequests = new Counter('scan_requests_total');
const scanSuccess = new Counter('scan_success_total');
const scanFailed = new Counter('scan_failed_total');
const pollRequests = new Counter('poll_requests_total');
const completedJobs = new Counter('completed_jobs_total');
const rewardsReceived = new Counter('rewards_received_total');

// Trends (latency)
const scanLatency = new Trend('scan_latency_ms');
const pollLatency = new Trend('poll_latency_ms');
const timeToComplete = new Trend('time_to_complete_ms');
const e2eLatency = new Trend('e2e_latency_ms');

// Rates
const scanSuccessRate = new Rate('scan_success_rate');
const completionRate = new Rate('completion_rate');
const rewardRate = new Rate('reward_rate');

// Gauges
const activeJobs = new Gauge('active_jobs');

// Stage counters
const stageVision = new Counter('stage_vision_count');
const stageRule = new Counter('stage_rule_count');
const stageAnswer = new Counter('stage_answer_count');
const stageReward = new Counter('stage_reward_count');
const stageDone = new Counter('stage_done_count');

// ============================================================================
// Test Options
// ============================================================================

export const options = {
  scenarios: {
    // VU 50 부하테스트
    load_test: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: TARGET_VUS },     // 30초간 target VU까지 증가
        { duration: TEST_DURATION, target: TARGET_VUS }, // 지정 시간동안 유지
        { duration: '30s', target: 0 },              // 30초간 종료
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    'scan_success_rate': ['rate>0.90'],           // 스캔 성공률 90% 이상
    'completion_rate': ['rate>0.85'],             // 완료율 85% 이상
    'scan_latency_ms': ['p(95)<5000'],            // 95% 스캔 5초 이내
    'time_to_complete_ms': ['p(95)<60000'],       // 95% 완료 60초 이내
    'e2e_latency_ms': ['p(95)<90000'],            // 95% E2E 90초 이내
  },
  // 태그 추가
  tags: {
    test_type: 'load_test',
    target_vus: String(TARGET_VUS),
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
  return `k6-load-${__VU}-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
}

/**
 * 결과 polling으로 완료 대기
 */
function waitForCompletion(jobId, startTime) {
  const maxAttempts = 30; // 최대 75초 (2.5초 * 30)
  const pollInterval = 2.5;

  let result = null;
  let completed = false;

  for (let i = 0; i < maxAttempts; i++) {
    const pollStart = Date.now();
    const res = http.get(
      `${BASE_URL}/api/v1/scan/result/${jobId}`,
      { headers: getHeaders(), timeout: '10s' }
    );
    pollLatency.add(Date.now() - pollStart);
    pollRequests.add(1);

    if (res.status === 200) {
      try {
        const data = JSON.parse(res.body);
        if (data.status === 'completed') {
          completed = true;
          result = data;

          // 스테이지 카운트
          stageVision.add(1);
          stageRule.add(1);
          stageAnswer.add(1);
          if (data.reward && data.reward.name) {
            stageReward.add(1);
            rewardsReceived.add(1);
          }
          stageDone.add(1);

          break;
        } else if (data.status === 'failed') {
          console.error(`[VU ${__VU}] Job failed: ${jobId}`);
          break;
        }
      } catch (e) {
        // JSON 파싱 실패
      }
    } else if (res.status === 404) {
      // 아직 처리 시작 안됨 - 계속 대기
    }

    sleep(pollInterval);
  }

  const elapsedMs = Date.now() - startTime;
  return {
    completed,
    result,
    elapsedMs,
    hasReward: result?.reward?.name ? true : false,
  };
}

// ============================================================================
// Main Test
// ============================================================================

export default function () {
  const iterStart = Date.now();

  // -------------------------------------------------------------------------
  // Step 1: POST /api/v1/scan
  // -------------------------------------------------------------------------
  const scanStart = Date.now();
  scanRequests.add(1);

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
  scanLatency.add(scanElapsed);

  const scanOk = check(scanRes, {
    'scan: status 200/202': (r) => r.status === 200 || r.status === 202,
    'scan: has job_id': (r) => {
      try {
        return JSON.parse(r.body).job_id !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  scanSuccessRate.add(scanOk);

  if (!scanOk) {
    scanFailed.add(1);
    console.error(`[VU ${__VU}] Scan failed: ${scanRes.status} - ${scanRes.body?.substring(0, 200)}`);
    completionRate.add(false);
    sleep(2);
    return;
  }

  scanSuccess.add(1);
  const scanData = JSON.parse(scanRes.body);
  const jobId = scanData.job_id;

  // Active jobs 추적
  activeJobs.add(1);

  // -------------------------------------------------------------------------
  // Step 2: 완료 대기 (Polling)
  // -------------------------------------------------------------------------
  const completionStart = Date.now();
  const completionResult = waitForCompletion(jobId, completionStart);

  timeToComplete.add(completionResult.elapsedMs);
  completionRate.add(completionResult.completed);
  rewardRate.add(completionResult.hasReward);

  if (completionResult.completed) {
    completedJobs.add(1);
  }

  // Active jobs 감소
  activeJobs.add(-1);

  // -------------------------------------------------------------------------
  // E2E 완료
  // -------------------------------------------------------------------------
  const e2eElapsed = Date.now() - iterStart;
  e2eLatency.add(e2eElapsed);

  // 로그 (10번에 1번만)
  if (__ITER % 10 === 0) {
    console.log(
      `[VU ${__VU}] Job ${jobId.substring(0, 8)}... ` +
      `completed=${completionResult.completed} ` +
      `reward=${completionResult.hasReward} ` +
      `time=${completionResult.elapsedMs}ms`
    );
  }

  // 다음 iteration 전 짧은 대기
  sleep(1 + Math.random());
}

// ============================================================================
// Setup & Teardown
// ============================================================================

export function setup() {
  console.log('========================================');
  console.log('SSE Load Test Starting');
  console.log(`Target VUs: ${TARGET_VUS}`);
  console.log(`Duration: ${TEST_DURATION}`);
  console.log(`Base URL: ${BASE_URL}`);
  console.log('========================================');

  // 토큰 검증
  if (!TOKEN) {
    throw new Error('TOKEN environment variable is required');
  }

  // API 연결 테스트
  const healthRes = http.get(`${BASE_URL}/health`, { timeout: '10s' });
  if (healthRes.status !== 200) {
    console.warn(`Health check failed: ${healthRes.status}`);
  }

  return { startTime: Date.now() };
}

export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log('========================================');
  console.log('SSE Load Test Completed');
  console.log(`Total Duration: ${duration.toFixed(1)}s`);
  console.log('========================================');
}

// ============================================================================
// Summary
// ============================================================================

export function handleSummary(data) {
  const timestamp = new Date().toISOString();

  const summary = {
    timestamp,
    config: {
      target_vus: TARGET_VUS,
      duration: TEST_DURATION,
      base_url: BASE_URL,
    },
    results: {
      scan: {
        total: data.metrics.scan_requests_total?.values?.count || 0,
        success: data.metrics.scan_success_total?.values?.count || 0,
        failed: data.metrics.scan_failed_total?.values?.count || 0,
        success_rate: (data.metrics.scan_success_rate?.values?.rate * 100 || 0).toFixed(2) + '%',
        latency_p50: (data.metrics.scan_latency_ms?.values?.['p(50)'] || 0).toFixed(0) + 'ms',
        latency_p95: (data.metrics.scan_latency_ms?.values?.['p(95)'] || 0).toFixed(0) + 'ms',
        latency_p99: (data.metrics.scan_latency_ms?.values?.['p(99)'] || 0).toFixed(0) + 'ms',
      },
      completion: {
        total: data.metrics.completed_jobs_total?.values?.count || 0,
        rate: (data.metrics.completion_rate?.values?.rate * 100 || 0).toFixed(2) + '%',
        time_p50: (data.metrics.time_to_complete_ms?.values?.['p(50)'] || 0).toFixed(0) + 'ms',
        time_p95: (data.metrics.time_to_complete_ms?.values?.['p(95)'] || 0).toFixed(0) + 'ms',
        time_p99: (data.metrics.time_to_complete_ms?.values?.['p(99)'] || 0).toFixed(0) + 'ms',
      },
      e2e: {
        latency_p50: (data.metrics.e2e_latency_ms?.values?.['p(50)'] || 0).toFixed(0) + 'ms',
        latency_p95: (data.metrics.e2e_latency_ms?.values?.['p(95)'] || 0).toFixed(0) + 'ms',
        latency_p99: (data.metrics.e2e_latency_ms?.values?.['p(99)'] || 0).toFixed(0) + 'ms',
      },
      rewards: {
        total: data.metrics.rewards_received_total?.values?.count || 0,
        rate: (data.metrics.reward_rate?.values?.rate * 100 || 0).toFixed(2) + '%',
      },
      stages: {
        vision: data.metrics.stage_vision_count?.values?.count || 0,
        rule: data.metrics.stage_rule_count?.values?.count || 0,
        answer: data.metrics.stage_answer_count?.values?.count || 0,
        reward: data.metrics.stage_reward_count?.values?.count || 0,
        done: data.metrics.stage_done_count?.values?.count || 0,
      },
      polling: {
        total_requests: data.metrics.poll_requests_total?.values?.count || 0,
        latency_p50: (data.metrics.poll_latency_ms?.values?.['p(50)'] || 0).toFixed(0) + 'ms',
        latency_p95: (data.metrics.poll_latency_ms?.values?.['p(95)'] || 0).toFixed(0) + 'ms',
      },
    },
    thresholds: data.thresholds,
  };

  // 콘솔 출력
  console.log('\n========== LOAD TEST SUMMARY ==========\n');
  console.log(JSON.stringify(summary, null, 2));
  console.log('\n=========================================\n');

  return {
    'stdout': JSON.stringify(summary, null, 2) + '\n',
    [`k6-load-test-vu${TARGET_VUS}-${timestamp.replace(/[:.]/g, '-')}.json`]: JSON.stringify(summary, null, 2),
  };
}
