// Package logging provides ECS-compatible structured logging for ext-authz.
package logging

import (
	"context"
	"io"
	"log/slog"
	"os"
	"time"
)

const (
	// Service metadata
	ServiceName    = "ext-authz"
	ServiceVersion = "1.0.7"
	ECSVersion     = "8.11"

	// Log levels
	LevelDebug = slog.LevelDebug
	LevelInfo  = slog.LevelInfo
	LevelWarn  = slog.LevelWarn
	LevelError = slog.LevelError
)

// Logger wraps slog.Logger with ECS-compatible defaults.
type Logger struct {
	*slog.Logger
}

// Config holds logger configuration.
type Config struct {
	Level       slog.Level
	Output      io.Writer
	Environment string
}

// DefaultConfig returns default logger configuration.
func DefaultConfig() *Config {
	return &Config{
		Level:       LevelInfo,
		Output:      os.Stdout,
		Environment: getEnv("ENVIRONMENT", "dev"),
	}
}

// New creates a new ECS-compatible logger.
func New(cfg *Config) *Logger {
	if cfg == nil {
		cfg = DefaultConfig()
	}

	opts := &slog.HandlerOptions{
		Level: cfg.Level,
		ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
			// ECS field mapping
			switch a.Key {
			case slog.TimeKey:
				// ECS uses @timestamp
				return slog.Attr{Key: "@timestamp", Value: a.Value}
			case slog.LevelKey:
				// ECS uses log.level
				return slog.Attr{Key: "log.level", Value: slog.StringValue(a.Value.String())}
			case slog.MessageKey:
				// ECS uses message
				return a
			}
			return a
		},
	}

	handler := slog.NewJSONHandler(cfg.Output, opts)
	baseLogger := slog.New(handler)

	// Add ECS base fields
	ecsLogger := baseLogger.With(
		slog.Group("ecs",
			slog.String("version", ECSVersion),
		),
		slog.Group("service",
			slog.String("name", ServiceName),
			slog.String("version", ServiceVersion),
			slog.String("environment", cfg.Environment),
		),
	)

	return &Logger{Logger: ecsLogger}
}

// WithContext returns a logger with context values (e.g., trace_id).
func (l *Logger) WithContext(ctx context.Context) *Logger {
	// Extract trace ID if available (from context or headers)
	// This can be extended to support OpenTelemetry trace context
	return l
}

// WithRequest returns a logger with HTTP request metadata.
func (l *Logger) WithRequest(method, path, host string) *Logger {
	return &Logger{
		Logger: l.With(
			slog.Group("http",
				slog.String("request.method", method),
				slog.String("url.path", path),
			),
			slog.String("host.name", host),
		),
	}
}

// WithUser returns a logger with user context (masked).
func (l *Logger) WithUser(userID, provider string) *Logger {
	return &Logger{
		Logger: l.With(
			slog.Group("user",
				slog.String("id", MaskUserID(userID)),
			),
			slog.String("auth.provider", provider),
		),
	}
}

// WithDuration returns a logger with duration information.
func (l *Logger) WithDuration(d time.Duration) *Logger {
	return &Logger{
		Logger: l.With(
			slog.Group("event",
				slog.Float64("duration_ms", float64(d.Microseconds())/1000),
			),
		),
	}
}

// AuthAllow logs an allowed authorization request.
func (l *Logger) AuthAllow(method, path, host, userID, provider, jti string, duration time.Duration) {
	l.WithRequest(method, path, host).
		WithUser(userID, provider).
		WithDuration(duration).
		Info("Authorization allowed",
			slog.String("event.action", "authorization"),
			slog.String("event.outcome", "success"),
			slog.String("token.jti", MaskJTI(jti)),
		)
}

// AuthDeny logs a denied authorization request.
func (l *Logger) AuthDeny(method, path, host, reason string, duration time.Duration, err error) {
	logger := l.WithRequest(method, path, host).WithDuration(duration)

	attrs := []any{
		slog.String("event.action", "authorization"),
		slog.String("event.outcome", "failure"),
		slog.String("event.reason", reason),
	}

	if err != nil {
		attrs = append(attrs, slog.String("error.message", err.Error()))
	}

	logger.Warn("Authorization denied", attrs...)
}

// AuthDenyWithUser logs a denied authorization with user context.
func (l *Logger) AuthDenyWithUser(method, path, host, userID, jti, reason string, duration time.Duration, err error) {
	logger := l.WithRequest(method, path, host).
		WithUser(userID, "").
		WithDuration(duration)

	attrs := []any{
		slog.String("event.action", "authorization"),
		slog.String("event.outcome", "failure"),
		slog.String("event.reason", reason),
		slog.String("token.jti", MaskJTI(jti)),
	}

	if err != nil {
		attrs = append(attrs, slog.String("error.message", err.Error()))
	}

	logger.Warn("Authorization denied", attrs...)
}

// getEnv returns environment variable or default value.
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// Global logger instance
var defaultLogger *Logger

// Init initializes the global logger.
func Init(cfg *Config) {
	defaultLogger = New(cfg)
}

// Default returns the global logger.
func Default() *Logger {
	if defaultLogger == nil {
		defaultLogger = New(nil)
	}
	return defaultLogger
}
