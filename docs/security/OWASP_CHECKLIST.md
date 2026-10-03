# Fieldnote Application Security Audit & OWASP Top 10 Verification

This document provides the security audit checklist and verification record for the Fieldnote Crop Health Application against the **OWASP Top 10 Web Application Security Risks**.

---

## 1. OWASP Top 10 Compliance Matrix

| Vulnerability Category | Risk Level | Fieldnote Implementation Control | Status |
| :--- | :--- | :--- | :--- |
| **A01: Broken Access Control** | High | Strict path traversal prevention, sandboxed file handlers, admin route segregation, and no direct object references. | **Compliant** |
| **A02: Cryptographic Failures** | High | Secrets stored exclusively in `.env`, TLS enforcement in Nginx proxy, EXIF GPS sanitization, zero plain-text storage. | **Compliant** |
| **A03: Injection** | High | Parameterized validation via Pydantic v2 schemas; no raw SQL or shell execution (`subprocess`) on user input. | **Compliant** |
| **A04: Insecure Design** | Medium | Privacy-first geolocation rounding (~1.1 km), explicit photo retraining consent toggles, and safe fallback logic. | **Compliant** |
| **A05: Security Misconfiguration** | High | Hardened Nginx headers (`CSP`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Permissions-Policy`), debug modes disabled in prod. | **Compliant** |
| **A06: Vulnerable & Outdated Components** | High | Automated CI dependency vulnerability scanning (`pip-audit`, `npm audit`), pinned dependencies with SHA verification. | **Compliant** |
| **A07: Identification & Auth Failures** | Medium | Session-less stateless token architecture, rate limiting per IP in Nginx reverse proxy (20 req/s with burst of 30). | **Compliant** |
| **A08: Software & Data Integrity Failures** | High | Model checksum verification, signed container builds, multi-stage Docker build with unprivileged `appuser`. | **Compliant** |
| **A09: Security Logging & Monitoring Failures** | Medium | Structured JSON logging in Nginx, zero PII logging in backend loggers, real-time error monitoring. | **Compliant** |
| **A10: Server-Side Request Forgery (SSRF)** | High | Outbound requests restricted strictly to whitelisted Open-Meteo weather API endpoints; no user-supplied URL fetching. | **Compliant** |

---

## 2. File Upload Sandboxing & Image Security

1. **Decompression Bomb Protection:**
   - Enforced `Image.MAX_IMAGE_PIXELS = 16_000_000` via Pillow in `backend/app/services/quality.py`.
   - Rejects payloads exceeding dimensions of $4000 \times 4000$ pixels with HTTP 413 / 400.
2. **MIME & Magic Byte Verification:**
   - Validates file headers for valid image formats (`JPEG`, `PNG`, `WebP`).
   - Rejects executable files disguised as images (`.exe`, `.sh`, `.php`, `.svg` with scripts).
3. **EXIF Metadata Stripping:**
   - Strips all camera serial numbers, GPS tags, timestamp data, and author strings during in-memory decode before model inference.

---

## 3. Privacy & Anti-Surveillance Controls

- **Coordinate Rounding:** Ingested latitude and longitude coordinates are rounded to 2 decimal places ($\approx 1.1\text{ km}$ precision at the equator) before storage or clustering.
- **Zero PII Policy:** No phone numbers, names, IP addresses, or farm boundary polygons are stored or logged.
- **Opt-In Photo Sharing:** Photos submitted with user feedback are only saved for active learning when `photo_consent: true` is explicitly provided.
