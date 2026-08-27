# HSLab CTF Classroom — Product Requirements Document (PRD)

Version 0.3 · Draft · Cập nhật: 2026-08-24
**Changelog v0.3:** Đưa **Multi-lab / Multi-tenant** vào trong phạm vi v1 (trước đây ở ngoài phạm vi). Đây là thay đổi nền tảng — mọi entity trong hệ thống giờ được scope theo **Tenant (Lab)**, thêm role **Super Admin** quản lý cấp hệ thống, và các phase đầu của roadmap được sắp xếp lại vì tenant scoping phải có từ đầu, không thể bolt-on sau.

---

## 1. Tổng quan

### 1.1 Bối cảnh
Lab hiện đang chạy chương trình CTF hàng tuần nhưng việc quản lý tiến độ, deadline, nhắc nhở và report đang làm thủ công. Ngoài ra, hệ thống được kỳ vọng phục vụ được **nhiều lab độc lập** trên cùng một lần triển khai (ví dụ nhiều lab CTF trong cùng trường, hoặc chia sẻ hạ tầng với lab khác trong tương lai) — mỗi lab có dữ liệu, thành viên, platform, deadline hoàn toàn tách biệt với nhau.

### 1.2 Mục tiêu
Xây dựng **HSLab CTF Classroom** — một "management layer" đa nền tảng (Platform Adapter) và **đa lab (multi-tenant)** nằm phía trên (các) nền tảng CTF:
- Một lần triển khai (deployment) có thể phục vụ **nhiều Lab (Tenant)** độc lập, dữ liệu tách biệt hoàn toàn.
- Mỗi Lab tự quản lý: thành viên, học kỳ, platform, challenge, tiến độ, deadline, reminder, report của riêng mình.
- Mỗi Lab tự chọn **1 platform CTF đang focus** riêng (không liên quan đến Lab khác).
- Có vai trò **Super Admin** ở cấp hệ thống để tạo/quản lý các Lab.

### 1.3 Phạm vi
**Trong phạm vi (MVP → v1):**
- **Tenant / Lab Management** (Super Admin tạo & quản lý các Lab, mỗi Lab có Lab Leader riêng)
- Platform Management (quản lý danh sách nền tảng CTF theo từng Lab, chọn platform đang focus **riêng cho từng Lab**)
- Quản lý Member / Semester / Challenge (gắn với 1 Lab + 1 platform cụ thể)
- Progress tracking (trạng thái Early/Done/Late/Missing)
- Sync tự động với platform đang focus (theo từng Lab)
- Reminder tự động trước deadline
- Weekly report tự động
- Email draft cho Lab Leader duyệt trước khi gửi giáo viên
- Semester report
- Dashboard tổng quan + trạng thái automation
- **Data isolation giữa các Lab** (không Lab nào nhìn thấy dữ liệu Lab khác)

**Ngoài phạm vi (chưa làm ở v1):**
- Sync đồng thời nhiều platform cùng lúc **trong cùng 1 Lab** (mỗi Lab vẫn chỉ 1 platform focus tại 1 thời điểm — ràng buộc này giữ nguyên, chỉ không còn giới hạn *toàn hệ thống chỉ 1 Lab*)
- Làm challenge ngay trong Classroom (nền tảng CTF vẫn là nơi giải bài)
- Mobile app riêng (web responsive là đủ)
- Chia sẻ Member/dữ liệu giữa các Lab (1 người dùng thuộc về đúng 1 Lab ở v1)
- Billing/subscription giữa các Lab (nội bộ, không phải mô hình SaaS trả phí)

### 1.4 Nguyên tắc thiết kế
1. **Tenant isolation là nguyên tắc gốc** — mọi entity, mọi query đều phải scope theo `tenant_id`; không có "quên lọc" — đây là rủi ro bảo mật nghiêm trọng nhất của hệ thống multi-tenant.
2. **Platform-agnostic core, single-focus per tenant** — mỗi Lab có adapter/platform riêng, không phụ thuộc Lab khác; trong 1 Lab chỉ 1 platform focus tại 1 thời điểm.
3. **Root Me là adapter đầu tiên**, không phải là thứ duy nhất được hardcode.
4. **Automation phải có Manual Override** trong phạm vi từng Lab.
5. **Không gửi email tự động ra ngoài lab mà không qua duyệt** — email cho giáo viên luôn ở trạng thái Draft chờ Lab Leader (của đúng Lab đó) approve.
6. **Dữ liệu lịch sử không đổi khi đổi focus platform** trong phạm vi 1 Lab.

---

## 2. Đối tượng người dùng (Personas)

| Role | Phạm vi | Mô tả | Quyền chính |
|---|---|---|---|
| **Super Admin** | Toàn hệ thống (không thuộc Lab nào) | Vận hành hệ thống, tạo Lab mới | Tạo/tạm khoá Lab, tạo Lab Leader ban đầu cho Lab mới, xem danh sách Lab (không xem chi tiết dữ liệu nội bộ từng Lab trừ khi cần hỗ trợ) |
| **Admin / Lab Leader** | Trong phạm vi 1 Lab | Quản lý toàn bộ Lab của mình | Full CRUD trong Lab, quản lý Platform, chọn/đổi focus platform, duyệt/gửi email, xem automation status |
| **Presenter** | Trong phạm vi 1 Lab | Member được phân công phụ trách 1 challenge/tuần | Cập nhật challenge mình phụ trách, xem tiến độ member khác cho challenge đó |
| **Member** | Trong phạm vi 1 Lab | Sinh viên trong lab | Xem challenge/deadline, tiến độ cá nhân, liên kết account platform |

> Một tài khoản (`email`) thuộc về đúng 1 Lab (trừ Super Admin không thuộc Lab nào). Không chia sẻ Member giữa các Lab ở v1.

---

## 3. Kiến trúc hệ thống

### 3.1 Thành phần chính
- **Web Frontend** — 3 khu vực: Super Admin console, Lab Admin dashboard, Member portal
- **Backend API** — xác thực đa tenant, business logic, CRUD, luôn scope theo `tenant_id` (trừ endpoint dành riêng cho Super Admin)
- **Database** — 1 database dùng chung, phân tách bằng cột `tenant_id` trên mọi bảng nghiệp vụ (shared schema, row-level isolation) — phù hợp quy mô "vài chục Lab" hơn là schema-per-tenant (phức tạp không cần thiết ở v1)
- **Platform Adapter Layer** — lớp trừu tượng hoá tích hợp nền tảng CTF, mỗi Lab cấu hình Platform độc lập
- **Sync Service** — worker định kỳ, chạy **theo từng Lab**, dùng adapter của platform đang focus của Lab đó
- **Scheduler / Job Queue** — chạy sync, reminder, report theo lịch cho từng Lab, có retry
- **Email Service** — gửi reminder, tạo draft report; cấu hình SMTP có thể **riêng theo từng Lab**

### 3.2 Tenant isolation — cơ chế thực thi
- Mọi bảng nghiệp vụ (`member`, `semester`, `challenge`, `platform`, `progress`, `reminder_log`, `report`, `sync_log`) có cột `tenant_id` trực tiếp (không chỉ suy ra qua join), để tầng service dễ enforce filter và giảm rủi ro leak dữ liệu.
- Tầng backend: mọi request (trừ Super Admin) đều gắn `tenant_id` lấy từ JWT/session của người dùng đăng nhập — **không bao giờ nhận `tenant_id` từ input của client**.
- Khuyến nghị bổ sung ở Phase hardening: bật **PostgreSQL Row-Level Security (RLS)** làm lớp phòng thủ thứ 2 ở tầng DB, phòng trường hợp code tầng service có bug quên filter.
- Super Admin không có `tenant_id` — các endpoint Super Admin tách biệt hoàn toàn (namespace riêng, ví dụ `/admin/*`), không dùng chung route với API nghiệp vụ của Lab.

### 3.3 Platform Adapter Pattern
(Không đổi so với v0.2, áp dụng độc lập theo từng Lab)
```
PlatformAdapter (interface)
  - resolve_user(username) -> external_user_id
  - get_user_completed_challenges(external_user_id) -> [external_challenge_id, ...]
  - get_challenge_detail(external_challenge_id) -> {title, score, category}

RootMeAdapter implements PlatformAdapter
TryHackMeAdapter implements PlatformAdapter   [tương lai]
```

### 3.4 Tech stack đề xuất
(Không đổi so với v0.2)

| Layer | Lựa chọn | Lý do |
|---|---|---|
| Backend | Python (FastAPI) | Nhẹ, nhanh, dễ viết middleware enforce tenant scoping |
| Background jobs | Celery + Redis | Retry đáng tin cậy, job chạy theo từng Lab (task nhận `tenant_id` làm tham số) |
| Frontend | Next.js (React) + TailwindCSS + shadcn/ui | Dev nhanh, dễ tách 3 khu vực UI (Super Admin / Lab Admin / Member) |
| Database | PostgreSQL | Hỗ trợ tốt Row-Level Security cho multi-tenant |
| Deployment | PM2 (process manager) + Cloudflare Tunnel, chạy trên máy WSL — xem chi tiết mục 3.6 | Không cần domain/IP tĩnh, tự khởi động lại khi WSL restart |
| Email | SMTP theo cấu hình riêng từng Lab (fallback SMTP mặc định của hệ thống nếu Lab chưa cấu hình) | Mỗi Lab có thể dùng email domain riêng |

### 3.5 Luồng dữ liệu
Super Admin tạo **Lab** → Lab Leader đăng nhập vào đúng Lab của mình → cấu hình **Platform** cho Lab đó → (Các) Platform → **Platform Adapter** (theo focus platform của Lab) → **Sync Service** (chạy theo `tenant_id`) → **Database** (đã scope tenant) → **Backend API** → **Frontend** (đúng context Lab đang đăng nhập).

### 3.6 Deployment operations — PM2 + Cloudflare Tunnel

> **Đây là yêu cầu triển khai cụ thể, dành cho người/AI implement đọc và tự tạo file — không phải mô tả tổng quát.** Môi trường chạy thật là máy cá nhân dùng **WSL** (không phải VPS/cloud có domain/IP tĩnh), nên cần Cloudflare Tunnel để expose app ra internet.

**Yêu cầu bắt buộc:**
1. Dùng **PM2** làm process manager, quản lý **3 process** (cập nhật từ v0.3: ban đầu chỉ 2, bổ sung `hslab-celery` khi Phase 3 đưa Celery vào scope):
   - `hslab-app` — app chính (backend/frontend).
   - `hslab-tunnel` — Cloudflare Tunnel để expose app ra 1 URL public HTTPS.
   - `hslab-celery` — Celery worker + beat gộp chung 1 process (`celery -A app.celery_app worker -B`), phục vụ sync tự động (Phase 3) và các job định kỳ sau này (reminder, report). Chấp nhận trade-off gộp worker+beat ở quy mô hiện tại (đơn giản hơn quản lý 4 process); nếu sau này cần tách riêng để tăng độ tin cậy, có thể tách thành `hslab-celery-worker` + `hslab-celery-beat` mà không đổi kiến trúc.
2. Cloudflare Tunnel mặc định chạy ở chế độ **Quick Tunnel** (không cần tài khoản/token, URL ngẫu nhiên `*.trycloudflare.com`, đổi mỗi lần restart). Nếu `.env` có khai báo token/credential Cloudflare (ví dụ để dùng Named Tunnel với domain cố định sau này), script phải **tự động chuyển sang chế độ đó** — không cần sửa code khi nâng cấp, chỉ cần điền `.env`.
3. Toàn bộ giá trị nhạy cảm (token Cloudflare, port app, lệnh khởi động app...) đọc từ file `.env` — kèm 1 file `.env.example` làm template (không chứa giá trị thật) để commit lên git.
4. **PM2 phải tự khởi động lại cả 3 process này khi WSL restart** (dùng `pm2 save` + `pm2 startup`; lưu ý WSL2 cần bật `systemd` trong `/etc/wsl.conf` để cơ chế này hoạt động — nếu không, cần phương án thay thế, ví dụ tự resurrect qua `~/.bashrc` hoặc Windows Task Scheduler).
5. **Đặt tên process rõ ràng, có tiền tố riêng của project** (`hslab-app`, `hslab-tunnel`, `hslab-celery`) — máy triển khai thực tế **đã có sẵn PM2 process khác đang chạy cho việc khác, không liên quan tới project này**. Mọi script/tài liệu hướng dẫn **không được dùng các lệnh phạm vi toàn cục** như `pm2 stop all`, `pm2 delete all`, `pm2 restart all`, `pm2 kill` — các lệnh này ảnh hưởng toàn bộ process trong PM2, kể cả process không thuộc project. Luôn thao tác theo đúng tên process cụ thể.

**Bắt buộc phải có `README.md` mô tả chi tiết, gồm ít nhất:**
- Cài đặt PM2 + `cloudflared` (client Cloudflare Tunnel).
- Cách cấu hình `.env` từ `.env.example`.
- Cách khởi động lần đầu, và các lệnh bật/tắt/restart/xem log **cho từng process riêng lẻ** theo tên.
- Cảnh báo rõ về việc không dùng lệnh PM2 phạm vi toàn cục (mục 5 ở trên).
- Cách bật auto-restart khi WSL khởi động lại (`pm2 save`, `pm2 startup`, lưu ý về `systemd` trên WSL2).
- **Cách truy vấn lại URL Quick Tunnel hiện tại sau khi process tunnel bị restart** (vì URL đổi ngẫu nhiên mỗi lần restart) — ví dụ đọc từ log của process tunnel để lấy dòng chứa `trycloudflare.com` mới nhất.
- Hướng dẫn nâng cấp sang Named Tunnel (URL cố định) khi cần dùng lâu dài, chỉ bằng cách điền token vào `.env`.

---

## 4. Tích hợp nền tảng CTF (Platform Integration)

*(Nội dung kỹ thuật không đổi so với v0.2 — chỉ khác: mọi Platform, mọi lần sync đều gắn với 1 `tenant_id` cụ thể, không có khái niệm platform "toàn hệ thống" nữa.)*

### 4.1 Platform Management (theo từng Lab)
- Mỗi Lab có danh sách Platform riêng, độc lập hoàn toàn với Lab khác.
- Chỉ 1 Platform có `is_focus = true` **trong phạm vi 1 Lab** tại 1 thời điểm.
- Đổi focus platform vẫn là hành động tường minh, có xác nhận, chỉ ảnh hưởng Lab đang thao tác.

### 4.2 Root Me Adapter

> **Tình trạng thực tế (2026-08-24): ĐÃ TEST THẬT với api_key thật — 2 kết luận quan trọng nhất của toàn bộ phần tích hợp Root Me đã được xác nhận (không còn là suy luận từ tài liệu nữa).**

> **✅ Xác nhận #1 — 1 api_key dùng chung cho tất cả member:** Test thật gọi `/auteurs/1` bằng key của 1 tài khoản khác, trả về đầy đủ data của `g0uZ` (tài khoản kỳ cựu Root Me, hoạt động 2006–2022, `membre: true`) — chứng minh **1 api_key tra được data public của bất kỳ user nào**, không giới hạn "chỉ xem chính chủ key". Giữ nguyên nguyên tắc: mỗi Lab chỉ cần **1 api_key** (từ 1 tài khoản Root Me do Lab tự tạo), Member chỉ cần cho biết username.

> **✅ Xác nhận #2 — CÓ timestamp chính xác, đây là tin rất tốt:** Response thật có tới 3 mảng riêng biệt: `challenges[]` (chỉ có `id_challenge`/`titre`/`url_challenge`, không ngày — đúng như ví dụ tài liệu chính thức show), `solutions[]` (writeup do user đăng, không liên quan), và **`validations[]`** — mảng này có `id_challenge`, `titre`, `id_rubrique`, và **`date`** dạng `"YYYY-MM-DD HH:MM:SS"` chính xác đến từng giây cho **mỗi lần giải challenge**. Kết luận trước đó của tôi (không có timestamp) là **sai**, vì tài liệu chính thức không hề nhắc đến sự tồn tại của `validations[]`. Thiết kế chính thức từ giờ: `completed_at = validations[].date` khớp theo `id_challenge`, **không cần fallback "thời điểm sync phát hiện" nữa** — status Early/Done/Late sẽ chính xác tuyệt đối, không phụ thuộc tần suất chạy sync.

> Cách lấy key: mỗi Lab tự đăng nhập tài khoản Root Me của mình (tài khoản dịch vụ do Lab tạo, không dùng tài khoản cá nhân) → vào `https://www.root-me.org/?page=preferences` → tạo API key tại đó.

> **Nguyên tắc bảo mật cố định — không thay đổi:** Hệ thống **KHÔNG BAO GIỜ** thu thập hay lưu password Root Me của Member. Chỉ cần **username** của Member (thông tin công khai) + **1 api_key duy nhất do Lab Admin quản lý** trong Platform config là đủ để lấy toàn bộ dữ liệu cần.

Root Me có official API tại `https://api.www.root-me.org`, xác thực bằng `api_key` truyền qua **cookie** (không phải query param hay Authorization header), ví dụ: `curl -b "api_key=***" https://api.www.root-me.org/auteurs/1`.

Endpoints và chiến lược sync giữ nguyên như v0.2, chỉ khác: job sync nhận thêm tham số `tenant_id`, chỉ xử lý Member/Challenge thuộc đúng Lab đó.

**Rate limit:** Root Me có thể trả lỗi `429 Too Many Requests` nếu 1 IP gọi quá nhiều request liên tục — `RootMeAdapter` cần rate-limit/backoff (gọi tuần tự có delay nhỏ hoặc chia batch), không gọi dồn toàn bộ member cùng lúc. Vì giờ đã có timestamp chính xác từ Root Me, tần suất sync chỉ ảnh hưởng **tốc độ phát hiện**, không ảnh hưởng **độ chính xác** — có thể giảm tần suất (ví dụ 1 lần/ngày) mà không lo sai lệch status.

> **Lưu ý quan trọng cho kiến trúc multi-tenant:** Root Me chặn theo **địa chỉ IP**, không phải theo `api_key`. Vì nhiều Lab chạy chung 1 server (chung 1 IP ra ngoài), rate-limit **phải là 1 hàng đợi/token-bucket dùng chung cho toàn hệ thống** (ví dụ qua Redis), không phải rate-limit riêng lẻ theo từng Lab — nếu không, tổng request cộng dồn từ nhiều Lab vẫn có thể khiến cả server dính `429` dù mỗi Lab tự thấy mình gọi ít.

### 4.2.1 Thuật toán đồng bộ chi tiết
1. **Không cần resolve tự động nữa:** `id_auteur` đã được Admin nhập trực tiếp (bắt buộc) khi tạo/sửa Member — xem mục 6.3. Nút "Tra cứu ID" chỉ là công cụ hỗ trợ lúc nhập liệu, không phải bước chạy ngầm trong luồng sync.
2. **Celery beat** chạy định kỳ (đề xuất mỗi ngày 1 lần là đủ, vì đã có timestamp chính xác — không cần sync dồn dập; có thể tăng tần suất nếu muốn phát hiện nhanh hơn, nhưng không bắt buộc vì độ chính xác), loop qua tất cả Lab active → với Lab đó, lấy platform đang focus + Member active có link account → đẩy mỗi Member thành 1 task vào hàng đợi (đi qua rate-limiter chung ở trên).
3. **Task xử lý từng Member:** gọi `GET /auteurs/{id_auteur}` với cookie `api_key` của Lab; nếu `429` → backoff & retry, lỗi 1 member không làm hỏng batch của member khác.
4. **Diff & cập nhật (dùng `validations[]`, không dùng `challenges[]`):** chỉ xét Challenge thuộc đúng `tenant_id` + `platform_id`, đang chưa `done`; với mỗi Challenge, tìm entry có `id_challenge` khớp trong `validations[]` → nếu có, lấy `date` của entry đó làm `completed_at` thật → tính `Progress.status` theo state machine (so `completed_at` với `deadline_at`), `detected_by = 'sync'`.
5. **Tôn trọng Manual Override:** nếu `Progress.detected_by` hiện tại là `manual`, sync **không ghi đè** — chỉ log lại để Admin biết có xung đột.
6. **Ghi `sync_log`** theo `tenant_id` + `platform_id`: số member check, số update, lỗi — hiển thị trên Dashboard.
7. **"Sync now" thủ công** dùng chung task/hàng đợi trên, có cooldown (đề xuất tối thiểu 15 phút/lần/Lab) để không tăng rủi ro rate-limit chung.
8. **[Tuỳ chọn, phase sau]** Tăng tần suất sync trong 24h cuối trước deadline để giảm độ trễ phát hiện Done gần mốc deadline.

### 4.3 Quy trình thêm nền tảng CTF mới
Không đổi so với v0.2 — thêm adapter mới có sẵn cho **mọi Lab** lựa chọn, nhưng việc bật/dùng là quyết định riêng của từng Lab.

---

## 5. Data Model (ERD)

```mermaid
erDiagram
  TENANT ||--o{ MEMBER : has
  TENANT ||--o{ SEMESTER : has
  TENANT ||--o{ PLATFORM : has
  TENANT ||--o{ CHALLENGE : has
  PLATFORM ||--o{ CHALLENGE : hosts
  PLATFORM ||--o{ MEMBER_PLATFORM_ACCOUNT : has
  MEMBER ||--o{ MEMBER_PLATFORM_ACCOUNT : links
  MEMBER ||--o{ PROGRESS : has
  MEMBER ||--o{ CHALLENGE : presents
  SEMESTER ||--o{ CHALLENGE : contains
  CHALLENGE ||--o{ PROGRESS : tracked_by
  SEMESTER ||--o{ REPORT : summarizes
  MEMBER ||--o{ REMINDER_LOG : receives

  TENANT {
    uuid id PK
    string name
    string slug
    boolean is_active
    jsonb smtp_config
    timestamp created_at
  }
  MEMBER {
    uuid id PK
    uuid tenant_id FK
    string full_name
    string email
    string password_hash
    string role
    boolean active
    timestamp joined_at
  }
  PLATFORM {
    uuid id PK
    uuid tenant_id FK
    string name
    string adapter_type
    string base_url
    boolean is_focus
    boolean is_active
    jsonb auth_config
  }
  MEMBER_PLATFORM_ACCOUNT {
  MEMBER_PLATFORM_ACCOUNT {
    uuid id PK
    uuid member_id FK
    uuid platform_id FK
    string external_username
    string external_user_id
  }
  SEMESTER {
    uuid id PK
    uuid tenant_id FK
    string name
    date start_date
    date end_date
    boolean is_current
  }
  CHALLENGE {
    uuid id PK
    uuid tenant_id FK
    uuid semester_id FK
    uuid platform_id FK
    int week_number
    string title
    string category
    string difficulty
    string external_challenge_id
    uuid presenter_id FK
    timestamp deadline_at
    int points
  }
  PROGRESS {
    uuid id PK
    uuid member_id FK
    uuid challenge_id FK
    string status
    timestamp completed_at
    string detected_by
    string note
  }
  REMINDER_LOG {
    uuid id PK
    uuid challenge_id FK
    uuid member_id FK
    timestamp sent_at
    string channel
  }
  REPORT {
    uuid id PK
    uuid tenant_id FK
    uuid semester_id FK
    string type
    date period_start
    date period_end
    timestamp generated_at
    string status
    text content
    string approved_by
  }
  SYNC_LOG {
    uuid id PK
    uuid tenant_id FK
    uuid platform_id FK
    timestamp run_at
    string status
    int members_checked
    text errors
  }
```

**So với v0.2:** thêm bảng `TENANT`; thêm cột `tenant_id` vào `MEMBER`, `PLATFORM`, `SEMESTER`, `CHALLENGE`, `REPORT`, `SYNC_LOG`; chính thức hoá cột `role` trên `MEMBER` (∈ `lab_leader`, `presenter`, `member`; Super Admin không nằm trong bảng này — xem mục 5.1).

> **Cập nhật từ Phase 1 (đã implement thật):** bổ sung `password_hash` vào `MEMBER` — thiếu sót của bản PRD gốc (chỉ ghi ở `SUPER_ADMIN`, quên ở `MEMBER`), cần thiết cho JWT auth. Ngoài ra: mỗi Lab mới được **tự động seed sẵn 1 Platform "Root Me" mặc định** (chưa cấu hình `auth_config`) ngay lúc tạo Lab, để Challenge Management ở Phase 1 hoạt động độc lập mà không cần chờ Platform Management (Phase 2). Đây là hành vi onboarding chính thức — Phase 2 sẽ làm cho Platform này **cấu hình được** (điền `api_key`, test connection), không cần bỏ đi.

> **Ràng buộc mới trên `MEMBER_PLATFORM_ACCOUNT.external_user_id` (bắt buộc, NOT NULL):** đây là `id_auteur` của Root Me — lưu ý: là **số dạng chuỗi** (ví dụ `"1"`, `"1119850"`), **không phải UUID chuẩn** dù đóng vai trò định danh duy nhất tương tự. Field này **bắt buộc phải nhập khi tạo/sửa liên kết account**, không được để trống hay chỉ dựa vào `external_username` — vì `id_auteur` bất biến còn username có thể đổi, và mọi lệnh gọi Root Me API (`/auteurs/{id_auteur}`) đều dùng ID này, không dùng username.

### 5.1 Super Admin — bảng riêng
Vì Super Admin không thuộc Lab nào, tách khỏi bảng `MEMBER` (vốn luôn có `tenant_id` bắt buộc):
```
SUPER_ADMIN
  id UUID PK
  email STRING
  password_hash STRING
  active BOOLEAN
```

`Progress.status`, `Progress.detected_by`, `Report.status` giữ nguyên như v0.2.

---

## 6. Chi tiết từng module chức năng

### 6.1 Tenant / Lab Management *(module mới)*
- **Super Admin console** (khu vực UI riêng biệt, không lẫn với dashboard của Lab):
  - Danh sách Lab: tên, slug, trạng thái active/inactive, ngày tạo.
  - Tạo Lab mới: nhập tên Lab + tạo tài khoản Lab Leader đầu tiên (email, mật khẩu tạm/invite link).
  - Tạm khoá 1 Lab (không xoá dữ liệu) nếu cần.
  - Super Admin **không** đi sâu vào dữ liệu nghiệp vụ của từng Lab (Member, Challenge...) trừ khi cần hỗ trợ kỹ thuật — giữ nguyên tắc tôn trọng ranh giới dữ liệu giữa các Lab.
- Đăng nhập: hệ thống xác định Lab của user qua tài khoản (email), điều hướng đúng context Lab đó; Super Admin đăng nhập vào console riêng.

### 6.2 Platform Management (theo Lab)
Giữ nguyên nội dung v0.2, scope theo `tenant_id` hiện tại.

### 6.3 Member Management
Giữ nguyên nội dung v0.2, thêm field `role` tường minh khi tạo member (lab_leader/presenter/member), luôn gắn `tenant_id` của Lab đang thao tác.

**Form liên kết Platform account (khi tạo/sửa Member):**
- **Root Me username** — nhập để tra cứu/hiển thị, không dùng để gọi API trực tiếp.
- **Root Me ID (`id_auteur`)** — **trường bắt buộc (NOT NULL)**, không cho lưu nếu để trống. Đây là ID số định danh duy nhất, dùng cho mọi lệnh gọi API sync — không dùng username vì username có thể đổi.
- Nút **"Tra cứu ID"** (tuỳ chọn hỗ trợ): gọi `/auteurs?nom=` để gợi ý `id_auteur` tương ứng với username đã nhập, nhưng Admin vẫn phải xác nhận/điền vào field trước khi lưu — hệ thống không tự ý điền ngầm mà không cho Admin thấy.
- Khuyến nghị (không bắt buộc ở v1): validate nhanh bằng cách gọi thử `/auteurs/{id_auteur}` khi lưu, cảnh báo nếu ID không tồn tại hoặc username trả về không khớp với username đã nhập (tránh gõ nhầm ID).

### 6.4 Semester Management
Giữ nguyên v0.2, scope theo `tenant_id`.

### 6.5 Challenge Management
Giữ nguyên v0.2, scope theo `tenant_id` + `platform_id` của Lab.

### 6.6 Progress Tracking
Giữ nguyên v0.2, scope theo `tenant_id` (qua member/challenge).

### 6.7 Platform Synchronization
Giữ nguyên v0.2, job Celery nhận thêm `tenant_id` — 1 lần chạy Celery beat sẽ loop qua tất cả Lab active, mỗi Lab sync độc lập (lỗi ở Lab A không ảnh hưởng Lab B).

### 6.8 Automatic Reminder
Giữ nguyên v0.2, scope theo `tenant_id`, dùng SMTP config riêng của Lab nếu có.

### 6.9 Weekly Report
Giữ nguyên v0.2, scope theo `tenant_id`.

### 6.10 Professor Email Draft
Giữ nguyên v0.2, chỉ Lab Leader **của đúng Lab đó** mới thấy và duyệt được draft của Lab mình.

### 6.11 Semester Report
Giữ nguyên v0.2, scope theo `tenant_id`.

### 6.12 Dashboard & Automation Status
Giữ nguyên v0.2 cho Lab Admin dashboard. Bổ sung: **Super Admin console** có dashboard riêng, đơn giản — chỉ hiện tổng số Lab active, Lab nào có automation đang lỗi kéo dài (để hỗ trợ kỹ thuật khi cần), không hiện chi tiết dữ liệu nghiệp vụ.

---

## 7. Yêu cầu phi chức năng (Non-functional)

- **Tenant isolation (bổ sung, ưu tiên cao nhất):** enforce `tenant_id` ở mọi tầng (service filter + khuyến nghị PostgreSQL RLS); viết test tự động kiểm tra không có endpoint nào leak dữ liệu chéo Lab trước khi release.
- **Bảo mật:** RBAC theo 4 role (super_admin/lab_leader/presenter/member); secrets (Platform config, SMTP) lưu riêng biệt theo từng Lab; HTTPS nội bộ.
- **Độ tin cậy:** retry + log lỗi cho mọi job; lỗi của 1 Lab không được làm gián đoạn xử lý các Lab khác (isolation cả về runtime, không chỉ dữ liệu).
- **Khả năng mở rộng:** thêm Lab mới không cần thay đổi code/hạ tầng, chỉ là 1 record `TENANT` mới.
- **Backup:** `pg_dump` định kỳ toàn database (chứa tất cả Lab); cân nhắc khả năng export/backup riêng theo từng Lab nếu cần restore độc lập.

---

## 8. Roadmap đề xuất (Phased delivery)

| Phase | Nội dung |
|---|---|
| **Phase 0** | Setup hạ tầng: PM2 + Cloudflare Tunnel (theo spec mục 3.6, kèm README.md), DB schema (đã có `tenant_id` từ đầu), CI cơ bản |
| **Phase 1 — MVP core + Multi-tenant nền tảng** | Bảng `TENANT`, `SUPER_ADMIN`, auth đa role, Super Admin console (tạo Lab), Member/Semester/Challenge CRUD scoped theo tenant, Progress nhập tay, Dashboard cơ bản |
| **Phase 2 — Platform layer** | `PlatformAdapter` interface, `RootMeAdapter`, Platform Management UI theo từng Lab, chọn focus platform |
| **Phase 3 — Sync tự động** | Celery beat sync loop qua tất cả Lab active, sync_log theo tenant, Manual Override |
| **Phase 4 — Automation** | Reminder tự động, Weekly Report tự động, Email Draft + luồng duyệt (SMTP theo Lab) |
| **Phase 5 — Report nâng cao** | Semester Report, export PDF/Excel |
| **Phase 6 — Hardening** | Bật PostgreSQL RLS, test tenant-isolation tự động, backup, alerting, tài liệu vận hành |

---

## 9. Rủi ro & câu hỏi mở

1. ✅ **[Đã xác nhận bằng test thật]** Root Me API trả timestamp chính xác lúc giải mỗi challenge, nằm trong mảng `validations[].date`. Xem chi tiết mục 4.2.
2. Presenter là role cố định hay chỉ là field gán theo từng Challenge? (giả định: field trên Challenge, không phải role hệ thống riêng)
3. Mỗi tuần có thể có nhiều challenge song song hay chỉ 1 challenge/tuần?
4. **[Mới]** Onboarding Lab mới: chỉ Super Admin tạo thủ công, hay có form self-service đăng ký Lab (cần duyệt)? PRD giả định **thủ công bởi Super Admin** ở v1.
5. **[Mới]** Một người có thể là Lab Leader của nhiều Lab cùng lúc không, hay 1 tài khoản luôn thuộc đúng 1 Lab? PRD giả định **1 tài khoản = 1 Lab** ở v1 (đơn giản hoá).
6. ✅ **[Đã xác nhận — Phase 6 hardening, 2026-08-25]** Không có, và sẽ không có, cơ chế Super Admin xem/thao tác dữ liệu nghiệp vụ (Member, Challenge, Progress, Report) của 1 Lab cụ thể — xác nhận bằng cách rà soát toàn bộ code: `admin/*` chỉ có 4 endpoint (auth, list/create/patch Lab, dashboard tổng hợp); `get_current_member` từ chối cứng mọi token có `scope=super_admin` (403); điểm chạm duy nhất của `admin/labs.py` vào bảng `members` là lúc `create_lab` — kiểm tra trùng email và tạo tài khoản Lab Leader đầu tiên (one-time provisioning theo đúng §6.1), không phải xem dữ liệu đã tồn tại. Đây là quyết định thiết kế cho v1, không phải khoảng trống: **không có tính năng impersonate**. Nếu sau này cần hỗ trợ debug sâu hơn, đây sẽ là một tính năng mới, có audit log riêng — không phải mở rộng cơ chế đã có.

---

## 10. Xu hướng thiết kế giao diện (UI/UX Direction)

Giữ nguyên định hướng ở v0.2 (dashboard sạch, hệ màu ngữ nghĩa Early/Done/Late/Missing, font monospace cho dữ liệu kỹ thuật, Progress Tracking dạng grid...). Bổ sung do multi-tenant:

- **Super Admin console tách biệt hoàn toàn về mặt thị giác** với dashboard của Lab — nên dùng theme neutral khác (ví dụ nền xám đậm hơn, không dùng màu accent của Lab UI) để không ai nhầm lẫn đang ở "chế độ vận hành hệ thống" hay "chế độ quản lý 1 Lab".
- Màn hình đăng nhập không cần chọn Lab thủ công — hệ thống tự nhận diện Lab qua tài khoản, giảm 1 bước thao tác.
- Trong Lab Admin dashboard, có thể thêm tên Lab nhỏ ở góc trên (giống "workspace name" trong các tool như Slack/Notion) để người dùng luôn biết mình đang ở Lab nào — dù ở v1 mỗi người chỉ thuộc 1 Lab, chi tiết này vẫn giúp rõ ràng và chuẩn bị sẵn cho trường hợp sau này 1 người thuộc nhiều Lab.
