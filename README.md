# SWA8 Cloud Integration — Home Assistant

تكامل يضيف **كل أجهزة حسابك على منصة mm.swabim.com** إلى Home Assistant. أي مستخدم عادي يملك حسابًا على المنصة يقدر:

- يعرض كل الأجهزة المرتبطة بحسابه في منزله (كأجهزة في Home Assistant).
- يتحكم فيها من خلال المنصة: تشغيل/إيقاف الريليات، المكيف (تشغيل + درجة حرارة)، ومتابعة الحساسات.

---

## ما الذي يتم إنشاؤه لكل جهاز (لوحة SWA8)

| النوع | الوصف | مثال الـ entity |
|-------|-------|-----------------|
| Switch × 8 | ريليات اللوحة (بالأسماء المحفوظة على الجهاز) | `switch.<device>_relay_1` |
| Switch | "All relays" — تشغيل/إيقاف كل الريليات دفعة واحدة | `switch.<device>_all_relays` |
| Switch | طاقة المكيف (AC Power) | `switch.<device>_ac_power` |
| Number | درجة حرارة المكيف (16–30°C) | `number.<device>_ac_temperature` |
| Sensor | الحرارة من حساس BMP280 (إن وُجد) | `sensor.<device>_temperature` |
| Sensor | الضغط من حساس BMP280 (إن وُجد) | `sensor.<device>_pressure` |
| Binary sensor | حالة الاتصال Online/Offline | `binary_sensor.<device>_online` |

> كل أجهزة نفس اللوحة تظهر مجمّعة تحت **جهاز واحد** في Home Assistant (Device Registry).

---

## 1) التثبيت

### الطريقة اليدوية (الأسهل)
1. انسخ مجلد `custom_components/swa8` كاملًا إلى مجلد `config` في Home Assistant:
   ```
   <config>/custom_components/swa8/
   ```
2. أعد تشغيل Home Assistant (أو اضغط Reload في Developer Tools).

### عبر HACS (إن كان مثبتًا)
1. HACS → Integrations → ⋮ → **Custom repositories**.
2. أضف رابط المستودع، النوع: **Integration**.
3. ثبّت، ثم أعد التشغيل.

> **ملاحظة:** إذا كان هناك نسخة قديمة من تكامل `swa8` مثبتة، احذف مجلدها أولًا ثم أعد التشغيل.

---

## 2) الإعداد

1. **Settings → Devices & Services → Add Integration**.
2. اختر **SWA8 Platform (Cloud)**.
3. أدخل **بريدك الإلكتروني وكلمة المرور** على `mm.swabim.com`.
4. اضغط Submit — سيتم جلب كل أجهزتك فورًا وإنشاء كل الـ entities.

> **دعم المصادقة الثنائية (2FA):** إذا كان حسابك مفعّل عليه المصادقة الثنائية، ستظهر خطوة إضافية بعد إدخال البريد وكلمة المرور تطلب **كود 6 أرقام** من تطبيق المصادقة. أدخل الكود واضغط Submit لإتمام الإعداد.

---

## 3) التحكم

- الريليات والمكيف تعمل **عبر المنصة** (`POST /api/devices/{key}/commands` على mm.swabim.com) — نفس القناة التي يستخدمها تطبيق الموبايل والموقع.
- تحديث الحالات كل **60 ثانية** افتراضيًا (يمكن تغييرها من **Options**، الحد الأدنى 15 ثانية).
- عند تشغيل/إيقاف أمر، تُحدَّث الحالة في الواجهة فورًا (optimistic) ثم يؤكد الجهاز القيمة الفعلية في الدورة التالية.
- **مزامنة تلقائية للأجهزة**: أي جهاز يُحذف من حسابك على المنصة يُزال تلقائيًا من Home Assistant في أول دورة تحديث تالية.

---

## 4) الخيارات / تغيير الحساب

- **Options** (⋮ بجوار التكامل): تغيير الإيميل/كلمة المرور، ومدة الفحص.
- إذا تغيرت كلمة المرور في المنصة، ستظهر شاشة **Re-authenticate** تلقائيًا.

---

## 5) حل المشاكل

| المشكلة | الحل |
|---------|------|
| "Cannot reach" أثناء الإعداد | تحقق من الإنترنت، وتأكد أن `https://mm.swabim.com` يعمل من المتصفح |
| "Invalid email or password" | تأكد من بيانات حسابك على mm.swabim.com |
| تظهر شاشة كود 6 أرقام | حسابك عليه مصادقة ثنائية — افتح تطبيق المصادقة وادخل الكود الحالي (كل 30 ثانية كود جديد) |
| الأجهزة لا تظهر | تأكد أن الأجهزة مربوطة بحسابك (من صفحة `/devices` على الموقع) وليست محذوفة |
| الحرارة/الضغط "غير معروف" | الجهاز ليس فيه حساس BMP280 — طبيعي |
| لا أرى التحكم المباشر لحظةً بلحظة | التكامل يعمل بـ polling كل دقيقة، وليس MQTT فوري |

---

## 6) ملاحظات تقنية

- **التوافق**: Home Assistant 2024.10+.
- **الاعتماديات**: لا شيء خارجي (يستخدم `aiohttp` المدمج).
- **الأمان**: كلمة المرور محفوظة في `config_entries` كما تفعل كل التكاملات، ولا تُرسل لأي مكان غير `https://mm.swabim.com/api/auth/login`. الجلسة تُجدد تلقائيًا عند انتهائها.
- **بنية الملفات**:

```
home-assistant/
├── README.md                 ← هذا الدليل
├── hacs.json                 ← تعريف HACS
└── custom_components/swa8/   ← التكامل نفسه
    ├── __init__.py           ← setup / unload
    ├── manifest.json
    ├── const.py
    ├── cloud.py              ← عميل REST لـ mm.swabim.com (login/devices/commands)
    ├── coordinator.py        ← جلب البيانات (polling)
    ├── config_flow.py        ← شاشة الإضافة + الخيارات + reauth
    ├── base.py               ← أساس الـ entities + DeviceInfo
    ├── switch.py / number.py / sensor.py / binary_sensor.py
    ├── diagnostics.py
    └── translations/ (en, ar)
```
