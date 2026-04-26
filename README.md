# Marketplace Backend API

This service is a small Flask backend that supports:

- User accounts (cookie-based sessions)
- A simple task marketplace (create / list / claim / submit)
- Optional World ID verification
- Agent polling for submitted task responses

## Base URL

- Local: `http://127.0.0.1:5000`
- Production (example): `https://lahacksbackend-production.up.railway.app`

All endpoints below are **JSON** and live under `/api/...`.

## CORS

The backend is configured to allow calls from any origin for `/api/*` and to support credentials (cookies).

## Authentication model

- Auth is **session-cookie** based.
- After `POST /api/auth/login`, the server sets a session cookie.
- Endpoints that require login use that cookie and will return **401** if missing.

When calling from a browser, use `fetch(..., { credentials: "include" })`.

## Task lifecycle (current)

The task `status` field uses:

- `open`: available to be claimed
- `claimed`: claimed by a human user (aka legacy "accepted")
- `submitted`: human submitted `response_text`
- `completed`: legacy completion endpoint (still exists)

## Error format

Most errors look like:

```json
{ "error": "message" }
```

Success responses usually look like:

```json
{ "message": "..." }
```

---

## Auth endpoints

### Register

- **POST** `/api/auth/register`
- **Body**

```json
{ "username": "string", "password": "string" }
```

- **Responses**
  - **200** `{"message":"User registered"}`
  - **400** `{"error":"Username already exists"}`

### Login

- **POST** `/api/auth/login`
- **Body**

```json
{ "username": "string", "password": "string" }
```

- **Responses**
  - **200** `{"message":"Logged in"}`
  - **401** `{"error":"Invalid credentials"}`

### Logout

- **POST** `/api/auth/logout`
- **Responses**
  - **200** `{"message":"Logged out"}`

### Current user

- **GET** `/api/auth/me`
- **Responses**
  - **200**

```json
{
  "username": "string",
  "world_id_verified": true,
  "fake_balance": 0.0
}
```

  - **401** `{"error":"Not logged in"}`

---

## Task endpoints

### Create task

- **POST** `/api/tasks/`
- **Body**

```json
{
  "description": "string",
  "compensation": 0.0,
  "requester_address": "string|null"
}
```

- **Notes**
  - `requester_address` is used by the agent polling flow to know who should receive the human response later.

- **Responses**
  - **200**

```json
{ "message": "Task created", "task_id": 123 }
```

### List tasks

- **GET** `/api/tasks/`
- **Response** (**200**)

```json
[
  {
    "id": 123,
    "description": "string",
    "status": "open|claimed|submitted|accepted|completed",
    "compensation": 0.0,
    "assigned_user": "username|null",
    "response_text": "string|null"
  }
]
```

- **Notes**
  - `response_text` is returned only when the task is `submitted` or `completed` (per current implementation).

### Claim task

- **POST** `/api/tasks/<task_id>/claim`
- **Auth required**: yes (session cookie)
- **Extra requirement**: user must have `world_id_verified=true`
- **Responses**
  - **200** `{"message":"Task claimed"}`
  - **401** `{"error":"Not logged in"}`
  - **403** `{"error":"World ID verification required"}`
  - **400** `{"error":"Task not available"}`

### Accept task (legacy)

- **POST** `/api/tasks/<task_id>/accept`
- Same behavior as claim, but returns message `"Task accepted"` and sets `status="claimed"`.

### Submit task response (text)

- **POST** `/api/tasks/<task_id>/submit`
- **Auth required**: yes (session cookie)
- **Body**

```json
{ "response_text": "string" }
```

- **Rules**
  - Task must exist
  - Task must be assigned to the logged-in user
  - Task must be in `claimed` (or legacy `accepted`) state

- **Responses**
  - **200** `{"message":"Task submitted"}`
  - **401** `{"error":"Not logged in"}`
  - **404** `{"error":"Task not found"}`
  - **400** `{"error":"Task not assigned to you"}` or `{"error":"response_text is required"}`

### Complete task (legacy)

- **POST** `/api/tasks/<task_id>/complete`
- **Auth required**: yes (session cookie)
- **Responses**
  - **200** `{"message":"Task completed, balance updated"}`
  - **401** `{"error":"Not logged in"}`
  - **400** `{"error":"Task not assigned to you"}`

---

## Agent polling endpoints (Option C)

These are used by an agent (or any client) to retrieve submitted responses for a given `requester_address` and to mark them delivered.

### List pending responses for requester

- **GET** `/api/tasks/responses/pending?requester_address=<requester_address>`
- **Query params**
  - `requester_address` (required)
- **Response** (**200**)

```json
[
  {
    "task_id": 123,
    "response_text": "string",
    "response_submitted_at": 1714090000
  }
]
```

- **Errors**
  - **400** `{"error":"requester_address is required"}`

### Mark a response as delivered

- **POST** `/api/tasks/<task_id>/responses/delivered`
- **Response**
  - **200** `{"message":"Marked delivered"}`
  - **200** `{"message":"Already delivered"}`
  - **404** `{"error":"Task not found"}`
  - **400** `{"error":"No submitted response for this task"}`

---

## World ID endpoints

### Get server config

- **GET** `/api/world/config`
- **Response** (**200**)

```json
{
  "configured": true,
  "app_id": "string",
  "rp_id": "string",
  "action": "string",
  "environment": "staging|production"
}
```

### Generate RP signature

- **POST** `/api/world/rp-signature`
- **Auth required**: yes
- **Body**

```json
{ "action": "verify-account" }
```

- **Responses**
  - **200**

```json
{
  "app_id": "string",
  "rp_id": "string",
  "action": "string",
  "environment": "staging|production",
  "sig": "0x...",
  "nonce": "0x...",
  "created_at": 1714090000,
  "expires_at": 1714090300
}
```

  - **401** `{"error":"Not logged in"}`
  - **503** `{"error":"World ID is not configured on the server"}`
  - **400** `{"error":"Invalid World ID action"}`
  - **500** `{"error":"Invalid World ID signing key"}`

### Verify user (World ID)

- **POST** `/api/world/verify`
- **Auth required**: yes
- **Body**

```json
{ "idkitResponse": { "...": "..." } }
```

- **Responses**
  - **200** `{"message":"World ID verified","verification":{...}}`
  - **401** `{"error":"Not logged in"}`
  - **503** `{"error":"World ID is not configured on the server"}`
  - **400** `{"error":"Missing IDKit response"}` / `{"error":"Invalid World ID action"}` / `{"error":"World ID verification failed", ...}`
  - **409** `{"error":"This World ID proof was already used"}`
  - **502** `{"error":"Could not reach World ID verification API", ...}`

---

## Quick curl examples

Replace `BASE` with your backend base URL.

### Register + login

```bash
curl -i -c cookies.txt -X POST "$BASE/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"pw"}'

curl -i -c cookies.txt -b cookies.txt -X POST "$BASE/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"pw"}'
```

### List tasks

```bash
curl -s "$BASE/api/tasks/" | jq .
```

### Claim + submit

```bash
curl -i -b cookies.txt -c cookies.txt -X POST "$BASE/api/tasks/123/claim"

curl -i -b cookies.txt -c cookies.txt -X POST "$BASE/api/tasks/123/submit" \
  -H 'Content-Type: application/json' \
  -d '{"response_text":"Done — here is the result..."}'
```

### Poll pending responses for a requester address

```bash
curl -s "$BASE/api/tasks/responses/pending?requester_address=agent1q..." | jq .
```

