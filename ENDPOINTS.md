# Marketplace Backend API Endpoints

## Authentication

### Register
- **POST** `/api/auth/register`
- **Body:** `{ "username": "string", "password": "string" }`
- **Response:** `{ "message": "User registered" }` or `{ "error": "Username already exists" }`

### Login
- **POST** `/api/auth/login`
- **Body:** `{ "username": "string", "password": "string" }`
- **Response:** `{ "message": "Logged in" }` or `{ "error": "Invalid credentials" }`
- **Notes:** Sets session cookie for authentication.

### Logout
- **POST** `/api/auth/logout`
- **Response:** `{ "message": "Logged out" }`

### Get Current User
- **GET** `/api/auth/me`
- **Response:** `{ "username": "string", "world_id_verified": bool, "fake_balance": float }` or `{ "error": "Not logged in" }`

---

## Tasks

### Create Task
- **POST** `/api/tasks/`
- **Body:** `{ "description": "string", "compensation": float, "requester_address": "string|null" }`
- **Response:** `{ "message": "Task created", "task_id": int }`

### List All Tasks
- **GET** `/api/tasks/`
- **Response:** `[{ "id": int, "description": "string", "status": "open|claimed|submitted|accepted|completed", "compensation": float, "assigned_user": "string|null", "response_text": "string|null" }]`

### Accept Task
- **POST** `/api/tasks/<task_id>/accept`
- **Auth required** (session cookie)
- **Response:** `{ "message": "Task accepted" }` or error
- **Notes:** User must be World ID verified

### Claim Task
- **POST** `/api/tasks/<task_id>/claim`
- **Auth required** (session cookie)
- **Response:** `{ "message": "Task claimed" }` or error
- **Notes:** User must be World ID verified

### Complete Task
- **POST** `/api/tasks/<task_id>/complete`
- **Auth required** (session cookie)
- **Response:** `{ "message": "Task completed, balance updated" }` or error

### Submit Task Response (text)
- **POST** `/api/tasks/<task_id>/submit`
- **Auth required** (session cookie)
- **Body:** `{ "response_text": "string" }`
- **Response:** `{ "message": "Task submitted", "delivered_to_requester": bool, "delivery_error": "string|null" }`
- **Notes:** If the server has `AGENT_WEBHOOK_URL` configured and the task was created with `requester_address`, the backend will POST the submission to the agent so the agent can message the original requester.

---

## World ID Verification

### Get World ID Client Config
- **GET** `/api/world/config`
- **Response:** `{ "configured": bool, "app_id": "string", "rp_id": "string", "action": "string", "environment": "staging|production" }`

### Generate RP Signature
- **POST** `/api/world/rp-signature`
- **Auth required** (session cookie)
- **Body:** `{ "action": "verify-account" }`
- **Response:** `{ "app_id": "string", "rp_id": "string", "action": "string", "environment": "string", "sig": "0x...", "nonce": "0x...", "created_at": int, "expires_at": int }`
- **Notes:** Requires `WORLD_ID_APP_ID`, `WORLD_ID_RP_ID`, and `WORLD_ID_SIGNING_KEY` in the backend environment.

### Verify User
- **POST** `/api/world/verify`
- **Auth required** (session cookie)
- **Body:** `{ "idkitResponse": { ... } }`
- **Response:** `{ "message": "World ID verified", "verification": { ... } }`
- **Notes:** Forwards the IDKit payload to World Developer Portal verification, then stores the proof nullifier so the same World ID cannot verify multiple accounts for the configured action.

---

## Notes
- All endpoints return JSON.
- Auth endpoints use session cookies for authentication.
- For demo, payment is simulated with a fake balance.
