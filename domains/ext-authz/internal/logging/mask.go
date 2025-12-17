package logging

import "strings"

const (
	// Masking configuration (aligned with Python implementation)
	MaskPlaceholder   = "***REDACTED***"
	MaskPreserveLen   = 4  // Characters to preserve at start/end
	MaskMinLength     = 10 // Minimum length for partial masking
)

// MaskJTI masks a JWT ID, preserving first and last characters.
// Example: "abc123def456" -> "abc1...f456"
func MaskJTI(jti string) string {
	return maskPartial(jti)
}

// MaskUserID masks a user ID for logging.
// UUIDs are partially masked, short IDs are fully masked.
// Example: "550e8400-e29b-41d4-a716-446655440000" -> "550e...0000"
func MaskUserID(userID string) string {
	return maskPartial(userID)
}

// MaskToken masks a JWT token, preserving only prefix.
// Example: "eyJhbGciOiJIUzI1NiJ9.xxx" -> "eyJh...REDACTED"
func MaskToken(token string) string {
	if token == "" {
		return MaskPlaceholder
	}

	// For tokens, only show first few chars
	if len(token) > MaskPreserveLen {
		return token[:MaskPreserveLen] + "..." + MaskPlaceholder
	}
	return MaskPlaceholder
}

// maskPartial applies partial masking to a string.
// If the string is shorter than MaskMinLength, it's fully masked.
// Otherwise, first and last MaskPreserveLen characters are preserved.
func maskPartial(s string) string {
	if s == "" {
		return MaskPlaceholder
	}

	// Remove any "Bearer " prefix
	s = strings.TrimPrefix(s, "Bearer ")
	s = strings.TrimPrefix(s, "bearer ")

	if len(s) < MaskMinLength {
		return MaskPlaceholder
	}

	prefix := s[:MaskPreserveLen]
	suffix := s[len(s)-MaskPreserveLen:]
	return prefix + "..." + suffix
}

// IsSensitiveKey checks if a key name indicates sensitive data.
// Aligned with Python SENSITIVE_FIELD_PATTERNS.
func IsSensitiveKey(key string) bool {
	lower := strings.ToLower(key)
	sensitivePatterns := []string{
		"password",
		"secret",
		"token",
		"api_key",
		"authorization",
	}

	for _, pattern := range sensitivePatterns {
		if strings.Contains(lower, pattern) {
			return true
		}
	}
	return false
}
