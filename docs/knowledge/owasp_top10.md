# OWASP Top 10 — Quick Reference

## A01 Broken Access Control
Restrict what authenticated users can do. Never trust client-supplied roles.
Always enforce server-side authorisation checks.

## A02 Cryptographic Failures
Use AES-256 for data at rest, TLS 1.2+ for transit. Never MD5/SHA-1 for passwords.
Use bcrypt, argon2id, or scrypt for password hashing.

## A03 Injection
Parametrise ALL database queries. Never concatenate user input into SQL strings.
Apply input validation on every external input boundary.

## A07 Identification & Authentication Failures
Implement MFA. Use short-lived JWTs. Rotate secrets regularly.

## A09 Security Logging & Monitoring Failures
Log all authentication events, privilege changes, and exceptions.
