#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Eco² E2E Intent Test Script
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Usage:
#   ./scripts/e2e-intent-test.sh <JWT_TOKEN>
#   ./scripts/e2e-intent-test.sh <JWT_TOKEN> --all    # Run all tests
#   ./scripts/e2e-intent-test.sh <JWT_TOKEN> --quick  # Quick test (WASTE, GENERAL)
#
# Description:
#   Intent별 E2E 테스트를 실행하고 SSE 이벤트를 검증합니다.
#
# Test Flow:
#   1. POST /api/v1/chat                    → chat_id 획득
#   2. POST /api/v1/chat/{chat_id}/messages → job_id 획득
#   3. GET  /api/v1/chat/{job_id}/events    → SSE 구독
#
# Intents Tested:
#   - WASTE: 분리배출 질문 (waste_rag + weather enrichment)
#   - CHARACTER: 캐릭터 정보 (gRPC)
#   - LOCATION: 장소 검색 (카카오맵 API)
#   - BULK_WASTE: 대형폐기물 (행정안전부 API)
#   - RECYCLABLE_PRICE: 재활용 시세 (환경공단 API)
#   - COLLECTION_POINT: 수거함 위치 (KECO API)
#   - WEB_SEARCH: 웹 검색 (Tavily/Brave)
#   - IMAGE_GENERATION: 이미지 생성 (OpenAI)
#   - GENERAL: 일반 대화
#   - MULTI_INTENT: 복합 질문 (병렬 처리)
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -e

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOKEN="${1:?Usage: $0 <JWT_TOKEN> [--all|--quick]}"
MODE="${2:-interactive}"
BASE_URL="${BASE_URL:-https://api.dev.growbin.app}"
SSE_TIMEOUT="${SSE_TIMEOUT:-60}"

# 서울 시청 좌표 (기본 위치)
DEFAULT_LOCATION='{"latitude":37.5665,"longitude":126.9780}'

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Colors & Logging
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }
event_log() { echo -e "${CYAN}[$1]${NC} $2"; }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API Functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 1. 채팅 생성
create_chat() {
    log "Creating new chat session..."
    response=$(curl -s -X POST "$BASE_URL/api/v1/chat" \
        -H "Content-Type: application/json" \
        -H "Cookie: s_access=$TOKEN")

    chat_id=$(echo "$response" | jq -r '.id // empty')
    if [ -z "$chat_id" ]; then
        err "Failed to create chat: $response"
        return 1
    fi

    log "chat_id: $chat_id"
    echo "$chat_id"
}

# 2. 메시지 전송 → job_id 획득
send_message() {
    local chat_id=$1
    local message=$2
    local location=$3  # optional JSON

    log "Sending message: \"$message\""

    if [ -n "$location" ]; then
        body=$(jq -n --arg msg "$message" --argjson loc "$location" \
            '{message: $msg, user_location: $loc}')
    else
        body=$(jq -n --arg msg "$message" '{message: $msg}')
    fi

    response=$(curl -s -X POST "$BASE_URL/api/v1/chat/$chat_id/messages" \
        -H "Content-Type: application/json" \
        -H "Cookie: s_access=$TOKEN" \
        -d "$body")

    job_id=$(echo "$response" | jq -r '.job_id // empty')
    stream_url=$(echo "$response" | jq -r '.stream_url // empty')

    if [ -z "$job_id" ]; then
        err "Failed to send message: $response"
        return 1
    fi

    log "job_id: $job_id"
    log "stream_url: $stream_url"
    echo "$job_id"
}

# 3. SSE 구독 및 이벤트 수신
subscribe_sse() {
    local job_id=$1
    local timeout=${2:-$SSE_TIMEOUT}

    log "Subscribing to SSE: /api/v1/chat/$job_id/events (timeout: ${timeout}s)"
    echo ""
    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│                     SSE Event Stream                        │"
    echo "├─────────────────────────────────────────────────────────────┤"

    local event_type=""
    local event_count=0
    local token_count=0
    local start_time=$(date +%s)

    timeout $timeout curl -s -N "$BASE_URL/api/v1/chat/$job_id/events" \
        -H "Cookie: s_access=$TOKEN" \
        -H "Accept: text/event-stream" 2>/dev/null | while IFS= read -r line; do

        # 이벤트 파싱
        if [[ "$line" == event:* ]]; then
            event_type="${line#event: }"
        elif [[ "$line" == data:* ]]; then
            data="${line#data: }"
            ((event_count++))

            # 이벤트 타입별 출력
            case "$event_type" in
                token)
                    ((token_count++))
                    content=$(echo "$data" | jq -r '.content // empty')
                    # 토큰은 간략하게 (매 10개마다 표시)
                    if [ $((token_count % 10)) -eq 1 ]; then
                        echo -ne "\r│ ${CYAN}[token]${NC} Streaming... (${token_count} tokens)"
                    fi
                    ;;
                keepalive)
                    # keepalive는 숨김
                    ;;
                done)
                    echo ""
                    event_log "$event_type" "$data"
                    log "Stream completed (${event_count} events, ${token_count} tokens)"
                    break
                    ;;
                error)
                    echo ""
                    err "$data"
                    break
                    ;;
                *)
                    # stage 이벤트 출력
                    stage=$(echo "$data" | jq -r '.stage // empty')
                    status=$(echo "$data" | jq -r '.status // empty')
                    progress=$(echo "$data" | jq -r '.progress // empty')
                    echo "│ ${YELLOW}[$event_type]${NC} stage=$stage status=$status progress=$progress"
                    ;;
            esac
        fi
    done

    echo "└─────────────────────────────────────────────────────────────┘"
    echo ""
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test Functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

test_intent() {
    local name=$1
    local message=$2
    local with_location=$3
    local expected_nodes=$4

    echo ""
    echo "╔═════════════════════════════════════════════════════════════╗"
    echo "║ Testing: $name"
    echo "║ Message: $message"
    echo "║ Expected: $expected_nodes"
    echo "╚═════════════════════════════════════════════════════════════╝"

    # 채팅 생성
    chat_id=$(create_chat)
    if [ -z "$chat_id" ]; then
        err "Test failed: $name (chat creation)"
        return 1
    fi

    # 위치 정보 설정
    local location=""
    if [ "$with_location" = "true" ]; then
        location="$DEFAULT_LOCATION"
        log "Using location: Seoul City Hall (37.5665, 126.9780)"
    fi

    # 메시지 전송
    job_id=$(send_message "$chat_id" "$message" "$location")
    if [ -z "$job_id" ]; then
        err "Test failed: $name (message send)"
        return 1
    fi

    # SSE 구독
    subscribe_sse "$job_id" "$SSE_TIMEOUT"

    log "Test completed: $name"
    return 0
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test Cases
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

run_test_waste() {
    test_intent "WASTE" \
        "플라스틱 분리배출 방법 알려줘" \
        "false" \
        "waste_rag, weather"
}

run_test_character() {
    test_intent "CHARACTER" \
        "플라스틱 버리면 어떤 캐릭터 얻어?" \
        "false" \
        "character"
}

run_test_location() {
    test_intent "LOCATION" \
        "근처 제로웨이스트샵 알려줘" \
        "true" \
        "location"
}

run_test_bulk_waste() {
    test_intent "BULK_WASTE" \
        "소파 버리려면 어떻게 해?" \
        "false" \
        "bulk_waste, weather"
}

run_test_recyclable_price() {
    test_intent "RECYCLABLE_PRICE" \
        "고철 시세 얼마야?" \
        "false" \
        "recyclable_price"
}

run_test_collection_point() {
    test_intent "COLLECTION_POINT" \
        "근처 의류수거함 어디야?" \
        "true" \
        "collection_point"
}

run_test_web_search() {
    test_intent "WEB_SEARCH" \
        "최신 분리배출 정책 알려줘" \
        "false" \
        "web_search"
}

run_test_image_generation() {
    test_intent "IMAGE_GENERATION" \
        "페트병 버리는 법 이미지로 만들어줘" \
        "false" \
        "image_generation"
}

run_test_general() {
    test_intent "GENERAL" \
        "안녕하세요" \
        "false" \
        "general"
}

run_test_multi_intent() {
    test_intent "MULTI_INTENT" \
        "종이 버리는 법이랑 수거함도 알려줘" \
        "true" \
        "waste_rag, collection_point, weather"
}

run_all_tests() {
    log "Running all intent tests..."
    local passed=0
    local failed=0

    for test_func in \
        run_test_waste \
        run_test_character \
        run_test_location \
        run_test_bulk_waste \
        run_test_recyclable_price \
        run_test_collection_point \
        run_test_web_search \
        run_test_image_generation \
        run_test_general \
        run_test_multi_intent
    do
        if $test_func; then
            ((passed++))
        else
            ((failed++))
        fi
        sleep 2  # Rate limiting
    done

    echo ""
    echo "╔═════════════════════════════════════════════════════════════╗"
    echo "║                    Test Summary                             ║"
    echo "╠═════════════════════════════════════════════════════════════╣"
    echo "║ Passed: $passed                                              "
    echo "║ Failed: $failed                                              "
    echo "╚═════════════════════════════════════════════════════════════╝"
}

run_quick_tests() {
    log "Running quick tests (WASTE, GENERAL)..."
    run_test_waste
    run_test_general
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
echo "╔═════════════════════════════════════════════════════════════╗"
echo "║              Eco² E2E Intent Test Suite                     ║"
echo "╠═════════════════════════════════════════════════════════════╣"
echo "║ Base URL: $BASE_URL"
echo "║ SSE Timeout: ${SSE_TIMEOUT}s"
echo "╚═════════════════════════════════════════════════════════════╝"
echo ""

# 연결 테스트
log "Testing API connectivity..."
health_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/chat" \
    -H "Cookie: s_access=$TOKEN" \
    -X GET 2>/dev/null || echo "000")

if [ "$health_code" = "000" ]; then
    err "Cannot connect to API server"
    exit 1
fi
log "API connection OK (HTTP $health_code)"

# 모드별 실행
case "$MODE" in
    --all)
        run_all_tests
        ;;
    --quick)
        run_quick_tests
        ;;
    *)
        # Interactive mode
        echo ""
        echo "Select test case:"
        echo "  1) WASTE - 분리배출 질문"
        echo "  2) CHARACTER - 캐릭터 정보"
        echo "  3) LOCATION - 장소 검색 (위치 필요)"
        echo "  4) BULK_WASTE - 대형폐기물"
        echo "  5) RECYCLABLE_PRICE - 재활용 시세"
        echo "  6) COLLECTION_POINT - 수거함 (위치 필요)"
        echo "  7) WEB_SEARCH - 웹 검색"
        echo "  8) IMAGE_GENERATION - 이미지 생성"
        echo "  9) GENERAL - 일반 대화"
        echo " 10) MULTI_INTENT - 복합 질문"
        echo " 11) Run ALL tests"
        echo " 12) Run QUICK tests"
        echo "  0) Exit"
        echo ""

        while true; do
            read -p "Enter choice [0-12]: " choice
            case $choice in
                1) run_test_waste ;;
                2) run_test_character ;;
                3) run_test_location ;;
                4) run_test_bulk_waste ;;
                5) run_test_recyclable_price ;;
                6) run_test_collection_point ;;
                7) run_test_web_search ;;
                8) run_test_image_generation ;;
                9) run_test_general ;;
                10) run_test_multi_intent ;;
                11) run_all_tests ;;
                12) run_quick_tests ;;
                0) exit 0 ;;
                *) warn "Invalid choice" ;;
            esac
            echo ""
        done
        ;;
esac
