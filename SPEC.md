# SPEC — Coffee Gear Price Tracker (ชื่อชั่วคราว: `coffee-price`)

เอกสารนี้เป็นสเปกสำหรับสร้างเว็บติดตามราคาอุปกรณ์กาแฟในไทย
เป้าหมายเชิงธุรกิจ: ทำรายได้จาก affiliate commission โดยมี traffic จาก SEO + LINE OA
เป้าหมายเชิงระบบ: รันได้เองแบบอัตโนมัติ (cron) ไม่ต้องมี manual operation รายวัน

---

## 0. ผลการตรวจสอบ BLOCKER (อัปเดต ก.ค. 2026)

### สิ่งที่ตรวจสอบแล้ว

| # | หัวข้อ | ผล | สถานะ |
|---|---|---|---|
| 1 | Shopee TH — cap ต่อ order | **225 บาท/คำสั่งซื้อ** (มีผล เม.ย. 2569) | 🟡 ผ่านแบบมีเงื่อนไข |
| 2 | Shopee TH — commission rate | ~2–3% (หมวด retail ทั่วไป) | ⚠️ ต้องยืนยันหมวดเครื่องใช้ไฟฟ้าใน portal |
| 3 | Cookie window | ~7–19 วัน | ✅ พอสำหรับสินค้าที่คนคิดนาน |

### ยังต้องยืนยันเอง (ทำใน affiliate portal)
- [ ] อัตรา commission **เฉพาะหมวดเครื่องใช้ไฟฟ้า / small appliance** (ตัวเลข 2–3% เป็นค่าเฉลี่ย retail อาจไม่ตรง)
- [ ] Lazada TH — cap ต่อ order เท่าไหร่ (ยังไม่มีข้อมูลสาธารณะชัดเจน)
- [ ] เงื่อนไข approval — รับเว็บ price comparison หรือไม่
- [ ] มี official Product API หรือไม่ (ถ้าไม่มี ต้องประเมินความเสี่ยง ToS ก่อน scrape)

### ผลกระทบต่อกลยุทธ์ — สำคัญมาก

เพดาน 225 บาท เริ่มกัดที่ราคาสินค้า:
```
225 บาท ÷ 3% = 7,500 บาท
```

**สินค้าราคาเกิน ~7,500 บาท ไม่ได้ค่าคอมฯ เพิ่มอีกเลย**

| สินค้า | ราคา | คอมฯ ที่ได้จริง | ประสิทธิภาพ |
|---|---|---|---|
| เครื่องบดมือหมุน | 3,000 | ~90 บ. | ยังไม่ชนเพดาน |
| **เครื่องบดไฟฟ้า** | **7,500** | **~225 บ.** | **จุดคุ้มที่สุด** |
| เครื่องชง entry | 15,000 | 225 บ. | เสียเปล่า 50% |
| เครื่องชง prosumer | 40,000 | 225 บ. | เสียเปล่า 85% |

**→ กลยุทธ์เปลี่ยน: เป้าหมายหลักคือสินค้าช่วง 4,000–10,000 บาท ไม่ใช่ของแพงสุด**

การเชียร์เครื่องชง 40,000 บาท ได้เงินเท่ากับเครื่องบด 7,500 บาท แต่ปิดการขายยากกว่ามาก (คนคิดนาน, conversion ต่ำ, มักไปซื้อผ่าน dealer)

### คณิตศาสตร์ใหม่
```
เป้า 15,000 บาท/เดือน ÷ 225 บาท/order = ~67 orders/เดือน
→ CVR 3% ของ clickout, clickout rate 30%
→ ต้องการ ~7,500 visitors/เดือน
```
เป็นไปได้จริงใน 6–9 เดือน (แผนเดิมที่เจาะของแพงต้องการ ~95,000 visitors)

---

## 1. Scope

### In scope
- ดึงราคาสินค้ารายวันจาก affiliate platform → เก็บ price history
- Generate หน้าเว็บอัตโนมัติจากฐานข้อมูล (product / compare / best-of / brand)
- กราฟราคาย้อนหลัง (นี่คือ unique value ที่คู่แข่งไม่มี)
- แจ้งเตือนราคาลดผ่าน LINE OA
- Clickout tracking (รู้ว่าหน้าไหนทำเงิน)

### Out of scope (อย่าทำในเฟสแรก)
- ระบบ user account / login
- ระบบรีวิวจากผู้ใช้
- Mobile app
- Multi-language

---

## 2. Stack

- **Backend:** Python 3.12 + FastAPI
- **ORM:** SQLModel
- **DB:** SQLite (WAL mode)
- **Template:** Jinja2
- **Frontend:** HTMX + plain CSS (ไม่มี build step)
- **Chart:** Chart.js ผ่าน CDN (ไม่ bundle)
- **Scheduler:** APScheduler (in-process) หรือ system cron
- **Deploy:** VPS ตัวเดียว + Caddy/nginx reverse proxy

หลักการ: **ไม่มี build step, ไม่มี node_modules, deploy ด้วย git pull + restart**

---

## 3. Data model

```sql
CREATE TABLE brand (
    id      INTEGER PRIMARY KEY,
    slug    TEXT NOT NULL UNIQUE,
    name    TEXT NOT NULL
);

CREATE TABLE product (
    id          INTEGER PRIMARY KEY,
    brand_id    INTEGER NOT NULL REFERENCES brand(id),
    slug        TEXT NOT NULL UNIQUE,
    name_th     TEXT NOT NULL,
    name_en     TEXT,
    category    TEXT NOT NULL,   -- espresso_machine | grinder | auto_machine | drip_gear | scale
    spec        TEXT,            -- JSON: burr_size, pressure, boiler_type, ฯลฯ
    msrp        INTEGER,         -- ราคาป้ายในบาท (nullable)
    -- คอมฯ ที่คาดว่าจะได้ = min(price * rate, CAP)  [CAP = 225]
    -- ใช้จัดลำดับความสำคัญของหน้า: หน้าไหนคุ้มค่าทำก่อน
    expected_commission INTEGER,
    created_at  DATETIME NOT NULL
);
CREATE INDEX idx_product_category ON product(category);
CREATE INDEX idx_product_comm ON product(expected_commission DESC);

CREATE TABLE listing (
    id              INTEGER PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES product(id),
    platform        TEXT NOT NULL,   -- shopee | lazada
    item_id         TEXT NOT NULL,   -- id ฝั่งแพลตฟอร์ม
    shop_name       TEXT,
    affiliate_url   TEXT NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT 1,
    last_seen_at    DATETIME,
    UNIQUE(platform, item_id)
);
CREATE INDEX idx_listing_product ON listing(product_id, active);

-- append-only: ห้าม UPDATE ห้าม DELETE
CREATE TABLE price_snapshot (
    id          INTEGER PRIMARY KEY,
    listing_id  INTEGER NOT NULL REFERENCES listing(id),
    captured_at DATETIME NOT NULL,
    price       INTEGER NOT NULL,   -- สตางค์ หรือ บาทเต็ม (เลือกอย่างใดอย่างหนึ่งแล้วยึดตลอด)
    in_stock    BOOLEAN NOT NULL
);
CREATE INDEX idx_snap_listing_time ON price_snapshot(listing_id, captured_at);

-- rollup รายวัน สำหรับ query กราฟให้เร็ว
CREATE TABLE price_daily (
    listing_id  INTEGER NOT NULL REFERENCES listing(id),
    day         DATE NOT NULL,
    min_price   INTEGER NOT NULL,
    max_price   INTEGER NOT NULL,
    PRIMARY KEY (listing_id, day)
);

CREATE TABLE alert (
    id           INTEGER PRIMARY KEY,
    line_user_id TEXT NOT NULL,
    product_id   INTEGER NOT NULL REFERENCES product(id),
    target_price INTEGER NOT NULL,
    active       BOOLEAN NOT NULL DEFAULT 1,
    created_at   DATETIME NOT NULL,
    notified_at  DATETIME
);
CREATE INDEX idx_alert_product ON alert(product_id, active);

CREATE TABLE clickout (
    id          INTEGER PRIMARY KEY,
    listing_id  INTEGER NOT NULL REFERENCES listing(id),
    ts          DATETIME NOT NULL,
    source_page TEXT NOT NULL,   -- path ของหน้าที่กดมา
    referrer    TEXT,
    ua_hash     TEXT             -- hash ของ user-agent + ip (ไม่เก็บ PII ดิบ)
);
CREATE INDEX idx_clickout_time ON clickout(ts);
CREATE INDEX idx_clickout_page ON clickout(source_page);
```

### กฎสำคัญ
1. `price_snapshot` เป็น **append-only** — เป็นสินทรัพย์ที่ทบต้นตามเวลา คู่แข่งหน้าใหม่ลอกไม่ได้
2. listing หายจากแพลตฟอร์ม → `active = 0` **ห้ามลบ** (ไม่งั้นกราฟขาด)
3. `clickout` ต้องมีตั้งแต่วันแรก — ถ้าไม่มี จะ optimize แบบเดาสุ่มไป 6 เดือน

---

## 4. Crawler

### Flow
```
cron (รายวัน 03:00 ICT)
  → ดึง listing ที่ active ทั้งหมด
  → เรียก platform API เป็น batch (respect rate limit)
  → insert price_snapshot
  → rollup เข้า price_daily
  → เช็ก alert ที่เข้าเงื่อนไข → ส่ง LINE push
  → invalidate page cache ของ product ที่ราคาเปลี่ยน
```

### ข้อกำหนด
- **ใช้ official Product API เท่านั้น** ถ้ามี (ดู §0)
- Rate limit + exponential backoff (base 2s, max 5 retry)
- Log ทุก failure ลง `crawl_log` (สร้างเพิ่มได้) — ต้องรู้ว่า listing ไหน fail ติดกันกี่วัน
- listing ที่ fail ติดกัน 7 วัน → `active = 0` อัตโนมัติ
- ความถี่: วันละครั้งพอ **ยกเว้น** ช่วง campaign (11.11, 12.12, 9.9) → ทุก 3 ชั่วโมง

### สิ่งที่ห้ามทำ
- ห้าม crawl ถี่กว่าที่จำเป็น (โดนบล็อก + เปลืองโควตา)
- ห้าม hardcode credential ในโค้ด → ใช้ `.env`

---

## 5. Page templates

| Template | Route | Keyword ที่จับ | จำนวนโดยประมาณ |
|---|---|---|---|
| Product | `/p/{slug}` | "[รุ่น] ราคา", "[รุ่น] ราคาถูกที่สุด" | ~300 |
| Compare | `/vs/{slug_a}-vs-{slug_b}` | "[A] vs [B]" | ~200 |
| Best-of | `/best/{category}-{budget}` | "เครื่องบดกาแฟ งบ 5000/8000/10000" | ~30 |
| Brand | `/brand/{slug}` | "[แบรนด์] ราคา" | ~20 |
| Guide | `/guide/{slug}` | คีย์เวิร์ดต้นน้ำ | ~15 |
| Home | `/` | brand term | 1 |

**เพดาน ~550 หน้า — อย่า generate เกินนี้ในเฟสแรก**
เว็บ pSEO ที่ตายคือเว็บที่ generate หน้าจาก SKU ที่ไม่มีใครค้นหา Google มองเป็น spam

### เนื้อหาบังคับในหน้า Product
1. ราคาปัจจุบันจากทุกร้าน เรียงจากถูกสุด
2. **กราฟราคาย้อนหลัง** (30 / 90 / 365 วัน) ← หัวใจของเว็บ
3. Verdict อัตโนมัติ: "ราคาตอนนี้ต่ำกว่าค่าเฉลี่ย 90 วัน X%" / "เคยลงต่ำสุดที่ Y บาท เมื่อ [วันที่]"
4. สเปกย่อ
5. ปุ่มตั้งแจ้งเตือนราคา (→ LINE)
6. Internal link ไปหน้า compare + best-of ที่เกี่ยวข้อง

### Compare page — เลือกคู่ที่ generate
อย่า generate ทุก permutation (N² ระเบิด) เลือกเฉพาะ:
- คู่ที่อยู่ category เดียวกัน **และ** ราคาต่างกันไม่เกิน 40%
- จำกัดสูงสุด 5 คู่ต่อ product

---

## 6. SEO requirements

- Server-rendered HTML ทั้งหมด (ไม่มี client-side rendering)
- `sitemap.xml` generate อัตโนมัติ + ping Search Console
- Structured data: `Product` + `Offer` + `AggregateOffer` (JSON-LD)
- Canonical URL ทุกหน้า
- Internal linking: หน้า guide (ต้นน้ำ) → best-of → product (ปลายน้ำ)
- Page cache: render แล้วเก็บเป็น static HTML, invalidate เมื่อราคาเปลี่ยน
- Core Web Vitals: ไม่มี JS framework, chart lazy-load

---

## 7. LINE OA

- ผู้ใช้กด "ตั้งแจ้งเตือน" บนหน้า product → LINE login → บันทึก `alert`
- Crawler เจอราคา ≤ `target_price` → push message + affiliate link
- Push message ต้องมี: ชื่อสินค้า, ราคาใหม่, ราคาเดิม, % ลด, ปุ่มไปซื้อ
- ป้องกัน spam: 1 alert แจ้งได้ 1 ครั้ง แล้ว `active = 0`

**นี่คือช่องทาง traffic ที่สอง ที่ไม่ขึ้นกับ Google** — ลดความเสี่ยงอัลกอริทึม

---

## 8. Clickout tracking

- ทุก affiliate link ต้องผ่าน `/go/{listing_id}?src={page_path}` → บันทึก `clickout` → 302 redirect
- Dashboard ภายใน `/admin/stats` (basic auth): clickout ต่อหน้า, ต่อสินค้า, ต่อวัน
- **ใช้ข้อมูลนี้ตัดสินใจ** ว่าจะขยายหน้าไหน ห้ามเดา

---

## 9. Config (`.env`)

```
DATABASE_URL=sqlite:///./data/app.db
AFFILIATE_PLATFORM=shopee
AFFILIATE_API_KEY=
AFFILIATE_API_SECRET=
AFFILIATE_TRACKING_ID=
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CHANNEL_SECRET=
CRAWL_HOUR=3
CRAWL_ENABLED=true
ADMIN_USER=
ADMIN_PASS=
BASE_URL=https://example.com
```

ใช้ Protocol abstraction สำหรับ affiliate platform เหมือนที่ทำใน `coffee-pos`:
```python
class AffiliateProvider(Protocol):
    def search_products(self, keyword: str) -> list[RawListing]: ...
    def fetch_prices(self, item_ids: list[str]) -> list[RawPrice]: ...
    def build_affiliate_url(self, item_id: str) -> str: ...
```
→ มี `MockProvider` สำหรับ dev, `ShopeeProvider` / `LazadaProvider` สำหรับ prod

---

## 10. Directory structure

```
coffee-price/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── routes/
│   │   ├── pages.py       # product, compare, best, brand, guide
│   │   ├── go.py          # clickout redirect
│   │   ├── line.py        # webhook + alert
│   │   └── admin.py
│   ├── crawler/
│   │   ├── runner.py
│   │   ├── providers/
│   │   │   ├── base.py    # Protocol
│   │   │   ├── mock.py
│   │   │   └── shopee.py
│   │   └── rollup.py
│   ├── seo/
│   │   ├── sitemap.py
│   │   └── jsonld.py
│   └── templates/
├── data/
│   ├── app.db
│   └── seed/
│       ├── products.csv   # seed สินค้าตั้งต้น
│       └── keywords.csv
├── static/
├── .env.example
└── SPEC.md
```

---

## 11. Milestones

### M1 — Foundation (สัปดาห์ 1–2)
- [ ] ยืนยัน BLOCKER §0 ผ่าน
- [ ] Schema + migration
- [ ] `MockProvider` + crawler รันได้ end-to-end
- [ ] Seed สินค้า 50 ตัวแรก (เครื่องบดก่อน — search volume สูงสุด)
- **DoD:** `python -m app.crawler.runner` แล้วมี snapshot ลง DB

### M2 — Real data (สัปดาห์ 3–4)
- [ ] `ShopeeProvider` / `LazadaProvider` ต่อ API จริง
- [ ] Cron ทำงานอัตโนมัติ
- [ ] Rollup + backoff + crawl log
- **DoD:** มีข้อมูลราคาต่อเนื่อง 14 วัน โดยไม่ต้องแตะมือ

### M3 — Pages (เดือน 2)
- [ ] Product page + กราฟราคา
- [ ] Compare, Best-of, Brand
- [ ] Clickout tracking + `/go/`
- [ ] sitemap + JSON-LD + submit Search Console
- **DoD:** Google index ได้ > 70% ของหน้าที่ submit

### M4 — LINE + ขยาย (เดือน 3–4)
- [ ] LINE OA + alert
- [ ] ขยาย SKU เป็น ~300
- [ ] Guide content 5–10 ชิ้น (เขียนเอง ไม่ generate)
- **DoD:** มี follower LINE + traffic organic เริ่มขึ้น

### M5 — Optimize (เดือน 5–6)
- [ ] อ่าน `clickout` → หาหน้าที่ทำเงิน
- [ ] ขยายเฉพาะหมวด/หน้าที่พิสูจน์แล้ว
- **DoD:** เห็น conversion จริงจาก affiliate dashboard

---

## 12. Seed keywords (ตั้งต้น)

**จัดลำดับตามเพดานคอมฯ 225 บาท — ของช่วง 4,000–10,000 บาทคือตัวทำเงิน**

### 🥇 Tier 1 — เครื่องบดกาแฟ (ตัวทำเงินหลัก)
สินค้าช่วง 4,000–10,000 ชนเพดานพอดี + คนเปลี่ยนบ่อย + ตัดสินใจเร็ว
- เครื่องบดกาแฟไฟฟ้า งบ 5000 / งบ 8000 / งบ 10000
- 1Zpresso JX-Pro ราคา / Timemore C3 ราคา / DF64 ราคา
- เครื่องบดกาแฟมือหมุน แนะนำ
- Timemore C3 vs 1Zpresso Q2
- เครื่องบดกาแฟ เอสเปรสโซ่ ตัวไหนดี

### 🥈 Tier 2 — เครื่องชงเอสเปรสโซ (ดึง traffic + authority)
**ไม่ใช่ตัวทำเงิน** (ชนเพดานเหมือนกันหมด) แต่ต้องมีเพื่อ topical authority
- เครื่องชงกาแฟ home barista แนะนำ
- Breville Bambino ราคา / Gaggia Classic ราคา
- เครื่องชงกาแฟ มือใหม่ ควรซื้ออะไร
→ ทุกหน้าต้อง internal link ไปหน้าเครื่องบด (คนซื้อเครื่องชงต้องซื้อเครื่องบดด้วยเสมอ — นี่คือ upsell path ที่ทำเงินจริง)

### 🥉 Tier 3 — Drip gear / accessories (ต้นน้ำ)
AOV ต่ำ ไม่ชนเพดาน แต่ traffic เยอะและแข่งง่าย
- อุปกรณ์ดริปกาแฟ เริ่มต้น
- V60 vs Kalita
- เครื่องชั่งกาแฟ แนะนำ
→ ใช้ดึงคนเข้า funnel แล้วส่งต่อไป Tier 1

> ตัวเลข search volume ต้องเช็กจริงด้วย Google Keyword Planner / Ahrefs ก่อนตัดสินใจสร้างหน้า — รายการนี้เป็นสมมติฐานตั้งต้น ยังไม่ใช่ข้อมูลยืนยัน

> ตัวเลข search volume ต้องไปเช็กจริงด้วยเครื่องมือ (Google Keyword Planner / Ahrefs) ก่อนตัดสินใจว่าจะสร้างหน้าไหน — รายการนี้เป็นสมมติฐานตั้งต้น ยังไม่ใช่ข้อมูลยืนยัน

---

## 13. ความเสี่ยงที่ต้องเฝ้า

| ความเสี่ยง | ผลกระทบ | การรับมือ |
|---|---|---|
| Commission cap ต่ำ | ฆ่าโปรเจกต์ | เช็กก่อนเริ่ม (§0) |
| Platform เปลี่ยนกติกา/ปิดโปรแกรม | รายได้เป็นศูนย์ | รองรับหลาย provider ผ่าน Protocol |
| Google algorithm update | traffic หาย | มี LINE เป็นช่องทางสอง |
| API โดน rate limit / บล็อก | ข้อมูลขาด | backoff + log + alert ตัวเอง |
| Thin content penalty | ไม่ติดอันดับ | ทุกหน้าต้องมีกราฟราคาจริง + guide เขียนเอง |
