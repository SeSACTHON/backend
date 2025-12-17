// Package constants provides centralized constant definitions for ext-authz.
package constants

// ============================================================================
// HTTP Headers
// ============================================================================

const (
	// Request headers
	HeaderAuthorization = "authorization"

	// Response headers (injected to upstream)
	HeaderUserID       = "x-user-id"
	HeaderAuthProvider = "x-auth-provider"
)

// ============================================================================
// HTTP Response Messages
// ============================================================================

const (
	// Error response bodies
	MsgMalformedRequest = "Malformed request"
	MsgMissingAuthHeader = "Missing Authorization header"
	MsgInvalidToken      = "Invalid token"
	MsgInternalError     = "Internal Authorization Error"
	MsgBlacklisted       = "Token is blacklisted"
)

// ============================================================================
// HTTP Paths
// ============================================================================

const (
	PathMetrics = "/metrics"
	PathHealth  = "/health"
	PathReady   = "/ready"
)

// ============================================================================
// Health Check
// ============================================================================

const (
	HealthOK = "ok"
)
