# coffee-price

เว็บติดตามราคาอุปกรณ์กาแฟ + affiliate
ดูสเปกเต็มที่ `SPEC.md`

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.seed              # seed สินค้าตั้งต้น 9 ตัว
python -m app.crawler.runner    # ดึงราคา -> price_snapshot -> price_daily
```

## สถานะ: M1 เสร็จ

- [x] Schema (SQLModel + SQLite WAL)
- [x] `AffiliateProvider` Protocol + `MockProvider`
- [x] Crawler runner: batch + exponential backoff + fail streak + crawl log
- [x] Rollup รายวัน (`price_daily`)
- [x] Seed script + `expected_commission`
- [ ] **M2:** `ShopeeProvider` / `LazadaProvider` — ติด BLOCKER §0
- [ ] **M3:** หน้าเว็บ + กราฟ + clickout
- [ ] **M4:** LINE OA alert

## สิ่งที่ต้องรู้ก่อนแตะโค้ด

**เพดานคอมฯ Shopee = 225 บาท/order** → เริ่มกัดที่ราคา ~7,500 บาท
สินค้าแพงกว่านั้นไม่ได้เงินเพิ่ม → **เป้าหมายหลักคือเครื่องบด 4,000–10,000 บาท ไม่ใช่เครื่องชงราคาแพง**

`expected_commission` ในตาราง `product` คำนวณจาก `min(msrp × rate, CAP)` ใช้จัดลำดับว่าควรทำหน้าไหนก่อน

## กฎที่ห้ามละเมิด

1. `price_snapshot` เป็น **append-only** — ห้าม UPDATE ห้าม DELETE
2. listing ที่หายจากแพลตฟอร์ม → `active = False` **ห้ามลบ** (ไม่งั้นกราฟขาด)
3. ใช้ `app.clock.utcnow()` เสมอ — ห้ามใช้ `datetime.utcnow()`
4. `clickout` ต้องมีตั้งแต่วันแรก — ไม่มี = optimize แบบเดาสุ่ม

## Structure

```
app/
├── config.py              # .env + expected_commission()
├── clock.py               # utcnow() -- tz-aware
├── models.py              # SQLModel
├── db.py                  # engine + init
├── seed.py                # seed สินค้าตั้งต้น
└── crawler/
    ├── runner.py          # cron entrypoint
    ├── rollup.py          # snapshot -> price_daily
    └── providers/
        ├── base.py        # Protocol
        └── mock.py        # dev / รอ affiliate อนุมัติ
```
