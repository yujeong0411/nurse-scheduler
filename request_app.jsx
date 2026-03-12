import { useState, useEffect } from "react";
import * as XLSX from "xlsx";

// ── 상수 ──
const NUM_DAYS = 28;
const WORK_SET = new Set(["D", "D9", "D1", "중1", "중2", "E", "N"]);
const SHIFT_ORDER = { "D": 1, "D9": 2, "D1": 2, "중1": 2, "중2": 2, "E": 3, "N": 4 };
const MID_D = new Set(["D", "D9", "D1", "중1", "중2"]);
const N_NO_NEXT = new Set(["보수", "필수", "번표"]);
const WD = ["월", "화", "수", "목", "금", "토", "일"];
const DEFAULT_RULES = { max_consecutive_work: 5, max_consecutive_N: 3, off_after_2N: 2, max_N_per_month: 6, min_weekly_off: 2, ban_reverse_order: true, public_holidays: [] };

const SHIFT_GROUPS = [
  { label: "근무", color: "#2563EB", shifts: ["D", "D9", "D1", "중2", "중1", "E", "N"] },
  { label: "휴무", color: "#D97706", shifts: ["OFF", "POFF", "법휴", "수면", "생휴", "휴가", "병가", "특휴", "공가", "경가"] },
  { label: "기타", color: "#6B7280", shifts: ["보수", "필수", "번표", "D제외", "E제외", "N제외"] },
];

const COLORS = {
  "D": { bg: "#EFF6FF", fg: "#1D4ED8", border: "#BFDBFE" },
  "D9": { bg: "#EFF6FF", fg: "#1E40AF", border: "#BFDBFE" },
  "D1": { bg: "#EFF6FF", fg: "#1E40AF", border: "#BFDBFE" },
  "E": { bg: "#F5F3FF", fg: "#6D28D9", border: "#DDD6FE" },
  "N": { bg: "#FEF2F2", fg: "#B91C1C", border: "#FECACA" },
  "중2": { bg: "#ECFEFF", fg: "#0E7490", border: "#A5F3FC" },
  "중1": { bg: "#ECFEFF", fg: "#155E75", border: "#A5F3FC" },
  "주": { bg: "#FEFCE8", fg: "#854D0E", border: "#FEF08A" },
  "OFF": { bg: "#F9FAFB", fg: "#374151", border: "#E5E7EB" },
  "POFF": { bg: "#F0FDF4", fg: "#166534", border: "#BBF7D0" },
  "법휴": { bg: "#FFF7ED", fg: "#9A3412", border: "#FED7AA" },
  "수면": { bg: "#EEF2FF", fg: "#3730A3", border: "#C7D2FE" },
  "생휴": { bg: "#FDF4FF", fg: "#86198F", border: "#F0ABFC" },
  "휴가": { bg: "#F0FDF4", fg: "#15803D", border: "#86EFAC" },
  "병가": { bg: "#F8FAFC", fg: "#334155", border: "#E2E8F0" },
  "특휴": { bg: "#F0FDFA", fg: "#115E59", border: "#99F6E4" },
  "공가": { bg: "#F7FEE7", fg: "#3F6212", border: "#D9F99D" },
  "경가": { bg: "#FFFBEB", fg: "#78350F", border: "#FDE68A" },
  "보수": { bg: "#FAFAF9", fg: "#44403C", border: "#E7E5E4" },
  "필수": { bg: "#FFF1F2", fg: "#9F1239", border: "#FECDD3" },
  "번표": { bg: "#FDF4FF", fg: "#701A75", border: "#F0ABFC" },
  "D제외": { bg: "#FEF2F2", fg: "#DC2626", border: "#FECACA" },
  "E제외": { bg: "#F5F3FF", fg: "#7C3AED", border: "#DDD6FE" },
  "N제외": { bg: "#FFF1F2", fg: "#BE123C", border: "#FECDD3" },
};

function sc(s) { return COLORS[s] || { bg: "#F9FAFB", fg: "#9CA3AF", border: "#E5E7EB" }; }
function fmtDate(d) {
  if (!d) return "";
  var dt = typeof d === "string" ? new Date(d) : d;
  return dt.getFullYear() + "." + String(dt.getMonth() + 1).padStart(2, "0") + "." + String(dt.getDate()).padStart(2, "0");
}
function getWd(sd, idx) { var d = new Date(sd); d.setDate(d.getDate() + idx - 1); return (d.getDay() + 6) % 7; }
function getDate(sd, idx) { var d = new Date(sd); d.setDate(d.getDate() + idx - 1); return d; }
function dlPassed(dl) { return dl ? new Date() > new Date(dl + "T23:59:59") : false; }
function mmdd(d) { return (d.getMonth() + 1) + "/" + d.getDate(); }

// 엑셀 불리언 파싱
function parseBool(val) {
  if (val === null || val === undefined) return false;
  if (typeof val === "boolean") return val;
  if (typeof val === "number") return val !== 0;
  var s = String(val).trim();
  return ["1", "O", "o", "Y", "y", "v", "V", "T", "t", "✓", "true", "TRUE", "예", "○", "◯", "x", "X"].indexOf(s) >= 0;
}

// [버그2 수정] 간호사 객체 정규화 — 필드 누락 방지
function normalizeNurse(n) {
  return {
    id: n.id || ("n_" + Date.now() + "_" + Math.random()),
    name: String(n.name || "").trim(),
    role: String(n.role || "").trim(),
    grade: String(n.grade || "").trim(),
    is_pregnant: typeof n.is_pregnant === "boolean" ? n.is_pregnant : parseBool(n.is_pregnant),
    is_male: typeof n.is_male === "boolean" ? n.is_male : parseBool(n.is_male),
    is_4day: typeof n.is_4day === "boolean" ? n.is_4day : parseBool(n.is_4day),
    fixed_weekly_off: (n.fixed_weekly_off === null || n.fixed_weekly_off === undefined) ? "" : String(n.fixed_weekly_off),
    vacation_days: parseInt(n.vacation_days) || 0,
  };
}

// 스토리지 안전 래퍼
// window.storage.get → {key,value,shared} 또는 throw (키 없음)
// window.storage.set → {key,value,shared} 또는 throw
function storageGet(key, shared) {
  return new Promise(function (resolve) {
    var done = false;
    var timer = setTimeout(function () { if (!done) { done = true; resolve(null); } }, 6000);
    window.storage.get(key, shared).then(function (res) {
      if (!done) { done = true; clearTimeout(timer); resolve(res || null); }
    }).catch(function () {
      if (!done) { done = true; clearTimeout(timer); resolve(null); }
    });
  });
}
function storageSet(key, val, shared) {
  return new Promise(function (resolve) {
    var done = false;
    var timer = setTimeout(function () { if (!done) { done = true; resolve(false); } }, 8000);
    window.storage.set(key, val, shared).then(function () {
      if (!done) { done = true; clearTimeout(timer); resolve(true); }
    }).catch(function (e) {
      if (!done) { done = true; clearTimeout(timer); resolve(false); }
      console.warn("storageSet failed:", key, e);
    });
  });
}

const IC = "w-full min-w-0 border-2 border-gray-200 rounded-xl px-4 py-3 text-base focus:outline-none focus:border-blue-500 bg-white";

// ── 검증 ──
function validate(shifts, day, s, nurse, rules, startDate) {
  if (!s) return [];
  var v = [];
  function g(d) { return shifts[d] || ""; }
  var iw = WORK_SET.has(s);
  if (iw && rules.ban_reverse_order) {
    var p = g(day - 1), nx = g(day + 1);
    if (day > 1 && SHIFT_ORDER[p] && SHIFT_ORDER[s] && SHIFT_ORDER[p] > SHIFT_ORDER[s]) v.push("역순 금지: " + (day - 1) + "일 " + p + "→" + day + "일 " + s);
    if (day < NUM_DAYS && SHIFT_ORDER[s] && SHIFT_ORDER[nx] && SHIFT_ORDER[s] > SHIFT_ORDER[nx]) v.push("역순 금지: " + day + "일 " + s + "→" + (day + 1) + "일 " + nx);
  }
  if (iw) {
    var c = 1, dd = day - 1; while (dd >= 1 && WORK_SET.has(g(dd))) { c++; dd--; } dd = day + 1; while (dd <= NUM_DAYS && WORK_SET.has(g(dd))) { c++; dd++; }
    if (c > rules.max_consecutive_work) v.push("연속근무 " + c + "일 (최대 " + rules.max_consecutive_work + "일)");
  }
  if (s === "N") {
    var cn = 1, dn = day - 1; while (dn >= 1 && g(dn) === "N") { cn++; dn--; } dn = day + 1; while (dn <= NUM_DAYS && g(dn) === "N") { cn++; dn++; }
    if (cn > rules.max_consecutive_N) v.push("연속 N " + cn + "개 (최대 " + rules.max_consecutive_N + "개)");
    var nc = Object.entries(shifts).filter(function (e) { return +e[0] !== day && e[1] === "N"; }).length + 1;
    if (nc > rules.max_N_per_month) v.push("월 N " + nc + "개 (최대 " + rules.max_N_per_month + "개)");
    function chk(from) {
      for (var k = 0; k < rules.off_after_2N; k++) {
        var c2 = from + k; if (c2 <= NUM_DAYS && WORK_SET.has(g(c2))) { v.push("NN 후 " + c2 + "일 근무"); break; }
      }
    }
    if (day > 1 && g(day - 1) === "N") chk(day + 1);
    if (day < NUM_DAYS && g(day + 1) === "N") chk(day + 2);
  }
  if (MID_D.has(s) && day >= 3) { var p2 = g(day - 2), p1 = g(day - 1); if (p2 === "N" && p1 && !WORK_SET.has(p1)) v.push("N→1휴→" + s + " 금지"); }
  if (s === "N" && day + 2 <= NUM_DAYS) { var n1 = g(day + 1), n2 = g(day + 2); if (n2 && MID_D.has(n2) && n1 && !WORK_SET.has(n1)) v.push("N→1휴→" + n2 + " 금지"); }
  if (N_NO_NEXT.has(s) && day >= 2 && g(day - 1) === "N") v.push("N 후 " + s + " 금지");
  if (s === "N" && day < NUM_DAYS && N_NO_NEXT.has(g(day + 1))) v.push("N 후 " + g(day + 1) + " 금지");
  if (s === "생휴") { if (nurse.is_male) v.push("생휴: 남성 불가"); if (Object.entries(shifts).filter(function (e) { return +e[0] !== day && e[1] === "생휴"; }).length >= 1) v.push("생휴: 월 1회 초과"); }
  if (s === "POFF" && !nurse.is_pregnant) v.push("POFF: 임산부만 가능");
  if (s === "중2") { if ((nurse.role || "").trim() !== "중2") v.push("중2: 역할 중2만 가능"); if (startDate && [5, 6].indexOf(getWd(startDate, day)) >= 0) v.push("중2: 주말 불가"); }
  if (s === "법휴" && !(rules.public_holidays || []).includes(day)) v.push("법휴: 공휴일 아님");
  if (s === "휴가") { var used = Object.entries(shifts).filter(function (e) { return +e[0] !== day && e[1] === "휴가"; }).length + 1; if (used > (nurse.vacation_days || 0)) v.push("휴가 잔여 초과"); }
  if (nurse.fixed_weekly_off != null && nurse.fixed_weekly_off !== "" && startDate) {
    var fw = parseInt(nurse.fixed_weekly_off);
    if (!isNaN(fw) && getWd(startDate, day) === fw && s !== "주") v.push("고정주휴(" + WD[fw] + "): 주만 가능");
  }
  return v;
}

// ══════════════════════════════════════════════
// Root
// ══════════════════════════════════════════════
export default function App() {
  var [page, setPage] = useState("landing");
  var [nurses, setNurses] = useState([]);
  var [rules, setRules] = useState(DEFAULT_RULES);
  var [startDate, setStartDate] = useState(null);
  var [deadline, setDeadline] = useState(null);
  var [ready, setReady] = useState(false);
  var [authedNurse, setAuthedNurse] = useState(null);

  useEffect(function () {
    (async function () {
      // [버그2 수정] 로드 시 normalizeNurse 적용
      var r1 = await storageGet("nurses", true);
      if (r1 && r1.value) {
        try { var parsed = JSON.parse(r1.value); setNurses(parsed.map(normalizeNurse)); } catch (e) { }
      }
      var r2 = await storageGet("rules", true); if (r2) setRules(Object.assign({}, DEFAULT_RULES, JSON.parse(r2.value)));
      var r3 = await storageGet("startDate", true); if (r3) setStartDate(r3.value);
      var r4 = await storageGet("deadline", true); if (r4) setDeadline(r4.value || null);
      setReady(true);
    })();
  }, []);

  var saveNurses = async function (ns) {
    var normalized = ns.map(normalizeNurse);
    setNurses(normalized); // 낙관적 업데이트
    var ok = await storageSet("nurses", JSON.stringify(normalized), true);
    if (!ok) console.warn("saveNurses: storageSet returned false");
  };
  var saveRules = async function (r) { setRules(r); await storageSet("rules", JSON.stringify(r), true); };
  var saveStartDate = async function (d) { setStartDate(d); await storageSet("startDate", d, true); };
  var saveDeadline = async function (d) { setDeadline(d || null); await storageSet("deadline", d || "", true); };

  if (!ready) return (
    <div className="flex h-screen items-center justify-center bg-gray-50">
      <div className="text-center"><div className="text-4xl mb-3">🏥</div><p className="text-gray-400 text-sm">로딩 중...</p></div>
    </div>
  );

  if (page === "nurse") {
    if (!authedNurse) return <NurseAuth nurses={nurses} onAuth={function (n) { setAuthedNurse(n); }} onBack={function () { setPage("landing"); }} />;
    return <NursePage nurse={authedNurse} rules={rules} startDate={startDate} deadline={deadline} onBack={function () { setPage("landing"); setAuthedNurse(null); }} />;
  }
  if (page === "admin") return <AdminPage nurses={nurses} saveNurses={saveNurses} rules={rules} saveRules={saveRules} startDate={startDate} saveStartDate={saveStartDate} deadline={deadline} saveDeadline={saveDeadline} onBack={function () { setPage("landing"); }} />;

  var passed = dlPassed(deadline);
  var endStr = startDate ? fmtDate(new Date(new Date(startDate).getTime() + 27 * 86400000)) : "";

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "linear-gradient(160deg,#1e3a8a 0%,#1d4ed8 50%,#2563eb 100%)" }}>
      <div className="flex-1 flex flex-col items-center justify-center px-6 pb-10 pt-16">
        <div className="text-center mb-12">
          <div className="w-24 h-24 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-2xl" style={{ background: "rgba(255,255,255,0.15)", backdropFilter: "blur(12px)", border: "1.5px solid rgba(255,255,255,0.25)" }}>
            <span style={{ fontSize: "44px" }}>🏥</span>
          </div>
          <h1 className="text-4xl font-bold text-white mb-2" style={{ letterSpacing: "-0.5px" }}>근무 신청</h1>
          <p className="text-blue-200 text-base">강남세브란스병원 응급실</p>
        </div>

        {startDate && (
          <div className="w-full max-w-sm mb-8 rounded-2xl px-5 py-4 text-center" style={{ background: "rgba(255,255,255,0.12)", backdropFilter: "blur(8px)", border: "1px solid rgba(255,255,255,0.2)" }}>
            <p className="text-blue-200 text-sm font-medium mb-1">신청 기간</p>
            <p className="text-white font-bold text-lg">{fmtDate(startDate)} ~ {endStr}</p>
            {deadline && (
              <div className={"inline-block mt-2.5 px-4 py-1.5 rounded-full text-sm font-bold " + (passed ? "bg-red-500 text-white" : "bg-yellow-400 text-yellow-900")}>
                {passed ? "⛔ 신청 마감됨" : "⏰ 마감 " + fmtDate(deadline)}
              </div>
            )}
          </div>
        )}

        <div className="w-full max-w-sm space-y-3">
          <button onClick={function () { setPage("nurse"); }}
            className="w-full bg-white text-blue-700 rounded-2xl font-bold text-xl shadow-2xl flex items-center justify-center gap-3 active:scale-95 transition-all"
            style={{ padding: "20px 24px" }}>
            <span style={{ fontSize: "26px" }}>📋</span> 근무 신청하기
          </button>
          <button onClick={function () { setPage("admin"); }}
            className="w-full text-white rounded-2xl font-semibold text-base flex items-center justify-center gap-2 active:scale-95 transition-all"
            style={{ padding: "16px 24px", background: "rgba(255,255,255,0.12)", border: "1.5px solid rgba(255,255,255,0.25)" }}>
            <span>⚙️</span> 관리자 모드
          </button>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════
// NurseAuth
// ══════════════════════════════════════════════
function NurseAuth(props) {
  var nurses = props.nurses, onAuth = props.onAuth, onBack = props.onBack;
  var [nurseId, setNurseId] = useState("");
  var [nurseName, setNurseName] = useState("");
  var [pin, setPin] = useState("");
  var [err, setErr] = useState("");
  var [loading, setLoading] = useState(false);
  var [showPicker, setShowPicker] = useState(false);

  var handleSelect = function (n) {
    setNurseId(n.id); setNurseName(n.name);
    setErr(""); setPin(""); setShowPicker(false);
  };

  var handleLogin = async function () {
    if (!nurseId) { setErr("이름을 선택해주세요."); return; }
    setLoading(true);
    try {
      var storedPin = "0000";
      var rp = await storageGet("pins", true);
      if (rp && rp.value) {
        try { var allPins = JSON.parse(rp.value); storedPin = allPins[nurseId] || "0000"; } catch (e) { }
      }
      if (pin === storedPin) {
        var found = nurses.find(function (n) { return n.id === nurseId; });
        onAuth(found);
      } else {
        setErr("PIN이 틀렸습니다."); setPin("");
      }
    } catch (e) {
      setErr("오류가 발생했습니다. 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "linear-gradient(160deg,#1e3a8a 0%,#1d4ed8 60%,#2563eb 100%)" }}>
      <div className="px-5 pt-12 pb-4">
        <button onClick={onBack} className="flex items-center gap-2 text-blue-200 font-medium" style={{ fontSize: "16px" }}>
          <span style={{ fontSize: "18px" }}>←</span> 돌아가기
        </button>
      </div>
      <div className="flex-1 flex flex-col justify-center px-5 pb-12">
        <div className="text-center mb-8">
          <div className="w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ background: "rgba(255,255,255,0.15)", border: "1.5px solid rgba(255,255,255,0.25)" }}>
            <span style={{ fontSize: "38px" }}>👤</span>
          </div>
          <h2 className="text-white font-bold mb-1" style={{ fontSize: "28px" }}>간호사 로그인</h2>
          <p className="text-blue-200" style={{ fontSize: "15px" }}>초기 PIN은 0000 입니다</p>
        </div>
        <div className="bg-white rounded-3xl shadow-2xl p-6 space-y-5">
          {/* 이름 선택 버튼 */}
          <div>
            <label className="font-bold text-gray-600 mb-2 block" style={{ fontSize: "15px" }}>이름 선택</label>
            <button onClick={function () { setShowPicker(true); }}
              className="w-full flex items-center justify-between rounded-xl px-4 text-left"
              style={{ border: "2px solid " + (nurseId ? "#2563EB" : "#E5E7EB"), background: nurseId ? "#EFF6FF" : "#F9FAFB", padding: "16px", minHeight: "56px" }}>
              <span style={{ fontSize: "17px", fontWeight: nurseId ? 700 : 400, color: nurseId ? "#1D4ED8" : "#9CA3AF" }}>
                {nurseName || "이름을 선택하세요 →"}
              </span>
              <span style={{ fontSize: "18px", color: "#6B7280" }}>▾</span>
            </button>
          </div>
          {/* PIN 입력 */}
          <div>
            <label className="font-bold text-gray-600 mb-2 block" style={{ fontSize: "15px" }}>PIN 번호</label>
            <input type="password" inputMode="numeric" maxLength={6} value={pin}
              onChange={function (e) { setPin(e.target.value.replace(/[^0-9]/g, "")); setErr(""); }}
              onKeyDown={function (e) { if (e.key === "Enter") handleLogin(); }}
              placeholder="● ● ● ●"
              style={{ width: "100%", border: "2px solid #E5E7EB", borderRadius: "12px", padding: "16px", textAlign: "center", fontSize: "28px", letterSpacing: "0.4em", boxSizing: "border-box", outline: "none" }}
            />
          </div>
          {err && <div className="rounded-xl px-4 py-3 text-center font-medium" style={{ background: "#FEF2F2", border: "1.5px solid #FECACA", color: "#DC2626", fontSize: "14px" }}>{err}</div>}
          <button onClick={handleLogin} disabled={loading || !nurseId}
            className="w-full rounded-xl font-bold"
            style={{ padding: "18px", fontSize: "17px", background: "#2563EB", color: "white", boxShadow: "0 4px 14px rgba(37,99,235,0.4)", opacity: (loading || !nurseId) ? 0.4 : 1 }}>
            {loading ? "확인 중..." : "로그인"}
          </button>
        </div>
      </div>

      {/* 이름 선택 모달 */}
      {showPicker && (
        <div className="fixed inset-0 z-50 flex flex-col justify-end" style={{ background: "rgba(0,0,0,0.5)" }} onClick={function () { setShowPicker(false); }}>
          <div className="bg-white rounded-t-3xl shadow-2xl" style={{ maxHeight: "70vh", display: "flex", flexDirection: "column" }} onClick={function (e) { e.stopPropagation(); }}>
            <div className="flex justify-center pt-3 pb-2"><div className="rounded-full" style={{ width: "48px", height: "6px", background: "#D1D5DB" }} /></div>
            <div className="px-5 py-3 border-b border-gray-100">
              <h3 className="font-black text-gray-900" style={{ fontSize: "20px" }}>이름 선택</h3>
              <p className="text-gray-400 mt-0.5" style={{ fontSize: "14px" }}>총 {nurses.length}명</p>
            </div>
            <div className="overflow-y-auto" style={{ flex: 1 }}>
              {nurses.length === 0 && (
                <div className="text-center py-12 text-gray-400" style={{ fontSize: "15px" }}>등록된 간호사가 없습니다.<br />관리자에게 문의하세요.</div>
              )}
              {nurses.map(function (n, i) {
                var isSel = n.id === nurseId;
                return (
                  <button key={n.id} onClick={function () { handleSelect(n); }}
                    className="w-full flex items-center justify-between px-5 text-left"
                    style={{ padding: "16px 20px", borderBottom: "1px solid #F3F4F6", background: isSel ? "#EFF6FF" : "white" }}>
                    <div>
                      <span style={{ fontSize: "17px", fontWeight: 700, color: isSel ? "#1D4ED8" : "#111827" }}>{n.name}</span>
                      {(n.grade || n.role) && <span className="ml-2" style={{ fontSize: "13px", color: "#6B7280" }}>{n.grade}{n.grade && n.role ? " · " : ""}{n.role}</span>}
                    </div>
                    {isSel && <span style={{ fontSize: "20px", color: "#2563EB" }}>✓</span>}
                  </button>
                );
              })}
              <div style={{ height: "24px" }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════
// NursePage — [버그3 수정] 탭 제거, 달력 단일 뷰
// ══════════════════════════════════════════════
function NursePage(props) {
  var nurse = props.nurse, rules = props.rules, startDate = props.startDate, deadline = props.deadline, onBack = props.onBack;
  var [shifts, setShifts] = useState({});
  var [picker, setPicker] = useState(null);
  var [saving, setSaving] = useState(false);
  var [saved, setSaved] = useState(false);
  var [loading, setLoading] = useState(false);
  var [showPin, setShowPin] = useState(false);
  var [toast, setToast] = useState("");
  var storageKey = startDate ? "req:" + nurse.id + ":" + startDate : null;
  var passed = dlPassed(deadline);

  var showToast = function (msg) { setToast(msg); setTimeout(function () { setToast(""); }, 3000); };

  useEffect(function () {
    if (!storageKey) return;
    setLoading(true);
    (async function () {
      var r = await storageGet(storageKey, true);
      setShifts(r && r.value ? JSON.parse(r.value).shifts || {} : {});
      setLoading(false);
    })();
  }, [storageKey]);

  var setShift = function (day, s) {
    setShifts(function (prev) {
      var next = Object.assign({}, prev);
      if (s) { next[day] = s; } else { delete next[day]; }
      return next;
    });
    setSaved(false);
  };

  var handleSubmit = async function () {
    if (!storageKey) { showToast("❌ 관리자가 시작일을 설정해야 합니다."); return; }
    if (passed) { showToast("❌ 신청 마감이 지났습니다."); return; }
    setSaving(true);
    var ok = await storageSet(storageKey, JSON.stringify({ shifts: shifts, submittedAt: new Date().toISOString(), nurseName: nurse.name }), true);
    if (ok) { setSaved(true); } else { showToast("❌ 저장 실패. 다시 시도해주세요."); }
    setSaving(false);
  };

  // 달력 셀 구성
  var startWd = startDate ? getWd(startDate, 1) : 0;
  var cells = [];
  for (var i = 0; i < startWd; i++) cells.push(null);
  for (var d = 1; d <= NUM_DAYS; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  // 통계
  var nCnt = 0, wCnt = 0, oCnt = 0;
  Object.entries(shifts).forEach(function (e) {
    if (e[1]) {
      if (WORK_SET.has(e[1])) wCnt++; else oCnt++;
      if (e[1] === "N") nCnt++;
    }
  });
  var reqCount = Object.keys(shifts).length;

  // 전체 위반 목록
  var allV = startDate ? Object.entries(shifts).reduce(function (acc, e) {
    validate(shifts, +e[0], e[1], nurse, rules, startDate).forEach(function (v) { acc.push(e[0] + "일: " + v); });
    return acc;
  }, []) : [];

  var endStr = startDate ? fmtDate(new Date(new Date(startDate).getTime() + 27 * 86400000)) : "";

  return (
    <div className="min-h-screen" style={{ background: "#F1F5F9" }}>
      {/* 헤더 */}
      <div className="sticky top-0 z-10 shadow-md" style={{ background: "linear-gradient(135deg,#1e3a8a,#2563eb)" }}>
        <div className="flex items-center gap-3 px-4 pt-5 pb-2">
          <button onClick={onBack} className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center text-white text-lg font-bold flex-shrink-0">←</button>
          <div className="flex-1">
            <h1 className="font-bold text-white leading-tight" style={{ fontSize: "22px" }}>{nurse.name}</h1>
            {startDate && <p className="text-blue-200 text-sm mt-0.5">{fmtDate(startDate)} ~ {endStr}</p>}
          </div>
          <button onClick={function () { setShowPin(true); }} className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0" style={{ fontSize: "18px" }} title="PIN 변경">🔐</button>
        </div>
        {/* 속성 태그 */}
        <div className="flex gap-2 px-4 pb-3 pt-1 flex-wrap">
          {nurse.grade && <span className="bg-white/20 text-white text-sm px-3 py-1 rounded-full font-medium">{nurse.grade}</span>}
          {nurse.role && <span className="bg-white/20 text-white text-sm px-3 py-1 rounded-full font-medium">{nurse.role}</span>}
          {(nurse.vacation_days || 0) > 0 && <span className="bg-white/20 text-white text-sm px-3 py-1 rounded-full font-medium">휴가 {nurse.vacation_days}일</span>}
          {nurse.is_pregnant && <span className="text-white text-sm px-3 py-1 rounded-full font-medium" style={{ background: "rgba(244,114,182,0.5)" }}>🤰 임산부</span>}
          {nurse.is_male && <span className="text-white text-sm px-3 py-1 rounded-full font-medium" style={{ background: "rgba(96,165,250,0.5)" }}>♂ 남성</span>}
          {nurse.is_4day && <span className="text-white text-sm px-3 py-1 rounded-full font-medium" style={{ background: "rgba(251,191,36,0.5)" }}>주4일</span>}
        </div>
      </div>

      {/* 마감 배너 */}
      {deadline && (
        <div className={"text-center py-3 font-bold " + (passed ? "bg-red-600 text-white" : "bg-yellow-400 text-yellow-900")} style={{ fontSize: "14px" }}>
          {passed ? "⛔ 신청이 마감되었습니다" : "⏰ 마감: " + fmtDate(deadline)}
        </div>
      )}

      {!startDate ? (
        <div className="flex flex-col items-center justify-center py-24 text-gray-400 text-center">
          <span className="text-5xl mb-3">⚙️</span>
          <p className="text-sm">관리자가 시작일을 설정해야 합니다.</p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center py-24 text-gray-400">
          <span className="text-2xl animate-spin mr-2">⏳</span>불러오는 중...
        </div>
      ) : (
        <div style={{ paddingBottom: "100px" }}>
          {/* 통계 바 */}
          <div className="grid grid-cols-4 gap-2 p-4">
            {[
              ["신청", reqCount, "#1D4ED8", "#EFF6FF", "#DBEAFE"],
              ["근무", wCnt, "#0369A1", "#F0F9FF", "#BAE6FD"],
              ["야간", nCnt, "#DC2626", "#FEF2F2", "#FECACA"],
              ["휴무", oCnt, "#B45309", "#FFFBEB", "#FDE68A"]
            ].map(function (r) {
              return (
                <div key={r[0]} className="rounded-2xl text-center py-3 px-1" style={{ background: r[2], boxShadow: "0 2px 8px rgba(0,0,0,0.12)" }}>
                  <div className="text-white font-black" style={{ fontSize: "26px", lineHeight: 1 }}>{r[1]}</div>
                  <div className="text-white/80 font-semibold mt-1" style={{ fontSize: "11px" }}>{r[0]}</div>
                </div>
              );
            })}
          </div>

          {/* 위반 목록 */}
          {allV.length > 0 && (
            <div className="mx-4 mb-3 rounded-2xl p-4" style={{ background: "#FEF2F2", border: "1.5px solid #FECACA" }}>
              <p className="font-bold text-red-700 mb-2" style={{ fontSize: "14px" }}>⚠️ 규칙 위반 {allV.length}건</p>
              {allV.slice(0, 3).map(function (v, i) { return <p key={i} className="text-red-600 mt-1" style={{ fontSize: "13px" }}>• {v}</p>; })}
              {allV.length > 3 && <p className="text-red-400 mt-1" style={{ fontSize: "12px" }}>외 {allV.length - 3}건...</p>}
            </div>
          )}
          {allV.length === 0 && reqCount > 0 && (
            <div className="mx-4 mb-3 rounded-2xl px-4 py-3" style={{ background: "#F0FDF4", border: "1.5px solid #BBF7D0" }}>
              <p className="font-semibold text-green-700" style={{ fontSize: "14px" }}>✓ 규칙 위반 없음</p>
            </div>
          )}

          {/* 달력 */}
          <div className="mx-4 bg-white rounded-2xl overflow-hidden" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.08)" }}>
            {/* 요일 헤더 */}
            <div className="grid grid-cols-7" style={{ background: "#1e3a8a" }}>
              {WD.map(function (wd, i) {
                return (
                  <div key={i} className="text-center font-bold py-2.5" style={{ fontSize: "13px", color: i === 5 ? "#93C5FD" : i === 6 ? "#FCA5A5" : "rgba(255,255,255,0.9)" }}>{wd}</div>
                );
              })}
            </div>
            {/* 날짜 셀 */}
            <div className="grid grid-cols-7" style={{ gap: "1px", background: "#E5E7EB" }}>
              {cells.map(function (day, i) {
                if (!day) return <div key={i} className="bg-white" style={{ minHeight: "72px" }} />;
                var wd = getWd(startDate, day);
                var isSat = wd === 5, isSun = wd === 6;
                var isHol = (rules.public_holidays || []).includes(day);
                var s = shifts[day] || "";
                var st = sc(s);
                var vs = s ? validate(shifts, day, s, nurse, rules, startDate) : [];
                var dateObj = getDate(startDate, day);
                var fixedWd = (nurse.fixed_weekly_off !== "" && nurse.fixed_weekly_off != null) ? parseInt(nurse.fixed_weekly_off) : -1;
                var isFixedOff = (!isNaN(fixedWd) && fixedWd >= 0 && wd === fixedWd);
                var dateColor = isSat ? "#3B82F6" : isSun || isHol ? "#EF4444" : "#374151";
                return isFixedOff ? (
                  <div key={i} className="flex flex-col items-center relative" style={{ minHeight: "72px", background: "#E5E7EB", cursor: "not-allowed", paddingTop: "6px" }}>
                    <span style={{ fontSize: "11px", fontWeight: 600, color: "#9CA3AF" }}>{mmdd(dateObj)}</span>
                    <span className="mt-1 rounded-lg font-bold w-4/5 text-center" style={{ background: "#9CA3AF", color: "white", fontSize: "11px", padding: "3px 2px" }}>주</span>
                    <span className="absolute bottom-1" style={{ fontSize: "9px" }}>🔒</span>
                  </div>
                ) : (
                  <button key={i}
                    onClick={function () { if (!passed) setPicker({ day: day }); }}
                    disabled={passed}
                    className="flex flex-col items-center relative active:opacity-60 transition-opacity"
                    style={{ minHeight: "72px", background: isHol || isSat || isSun ? "#EFF6FF" : "#FFFFFF", paddingTop: "6px" }}>
                    <span style={{ fontSize: "12px", fontWeight: 700, color: dateColor }}>{mmdd(dateObj)}</span>
                    {s ? (
                      <span className="mt-1 rounded-lg font-bold w-4/5 text-center" style={{ background: st.fg, color: "white", fontSize: "12px", padding: "3px 2px", letterSpacing: "-0.3px" }}>
                        {s}
                      </span>
                    ) : (
                      <span className="mt-1.5 flex items-center justify-center rounded-full" style={{ width: "24px", height: "24px", border: "2px dashed #D1D5DB", color: "#D1D5DB", fontSize: "14px" }}>
                        +
                      </span>
                    )}
                    {vs.length > 0 && (
                      <span className="absolute top-1 right-1 bg-red-500 rounded-full flex items-center justify-center text-white font-black" style={{ width: "16px", height: "16px", fontSize: "9px" }}>!</span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 신청 내역 리스트 */}
          {reqCount > 0 && (
            <div className="mx-4 mt-3 bg-white rounded-2xl p-4" style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
              <p className="font-bold text-gray-600 mb-3" style={{ fontSize: "14px" }}>신청 내역</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(shifts).sort(function (a, b) { return +a[0] - +b[0]; }).map(function (e) {
                  var st2 = sc(e[1]);
                  var dObj = getDate(startDate, +e[0]);
                  return (
                    <span key={e[0]} className="rounded-xl font-semibold border" style={{ background: st2.bg, color: st2.fg, borderColor: st2.border, fontSize: "13px", padding: "5px 10px" }}>
                      {mmdd(dObj)} {e[1]}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 제출 버튼 */}
      {startDate && !passed && (
        <div className="fixed bottom-0 left-0 right-0 px-4 pb-6 pt-3" style={{ background: "rgba(255,255,255,0.95)", backdropFilter: "blur(8px)", borderTop: "1px solid #E5E7EB" }}>
          <button onClick={handleSubmit} disabled={saving}
            className="w-full rounded-2xl font-bold transition-all active:scale-95"
            style={{
              padding: "18px",
              fontSize: "17px",
              background: saved ? "#16A34A" : "#2563EB",
              color: "white",
              boxShadow: saved ? "0 4px 14px rgba(22,163,74,0.4)" : "0 4px 14px rgba(37,99,235,0.4)",
              opacity: saving ? 0.7 : 1
            }}>
            {saving ? "저장 중..." : saved ? "✅ 신청 완료 (재저장 가능)" : "📨 신청 제출하기"}
          </button>
        </div>
      )}

      {picker && (
        <ShiftSheet
          day={picker.day}
          shifts={shifts}
          nurse={nurse}
          rules={rules}
          startDate={startDate}
          onSelect={function (s) { setShift(picker.day, s); setPicker(null); }}
          onClose={function () { setPicker(null); }}
        />
      )}
      {showPin && <PinModal nurseId={nurse.id} onClose={function () { setShowPin(false); }} />}
      {toast && (
        <div className="fixed top-4 left-4 right-4 z-50 flex justify-center" style={{ pointerEvents: "none" }}>
          <div className="rounded-2xl px-5 py-3 shadow-lg font-semibold text-sm" style={{ background: toast.startsWith("❌") ? "#FEF2F2" : "#F0FDF4", color: toast.startsWith("❌") ? "#DC2626" : "#16A34A", border: "1.5px solid " + (toast.startsWith("❌") ? "#FECACA" : "#BBF7D0"), pointerEvents: "auto" }}>{toast}</div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════
// ShiftSheet
// ══════════════════════════════════════════════
function ShiftSheet(props) {
  var day = props.day, shifts = props.shifts, nurse = props.nurse, rules = props.rules, startDate = props.startDate, onSelect = props.onSelect, onClose = props.onClose;
  var [confirm, setConfirm] = useState(null);
  var wd = getWd(startDate, day);
  var dateObj = getDate(startDate, day);
  var isHol = (rules.public_holidays || []).includes(day);
  var current = shifts[day] || "";

  var handlePick = function (s) {
    if (s === current) { onSelect(""); return; }
    var ps = Object.assign({}, shifts); delete ps[day];
    var vs = validate(ps, day, s, nurse, rules, startDate);
    if (vs.length > 0) { setConfirm({ shift: s, violations: vs }); return; }
    onSelect(s);
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div className="bg-white rounded-t-3xl shadow-2xl flex flex-col" style={{ maxHeight: "85vh" }} onClick={function (e) { e.stopPropagation(); }}>
        <div className="flex justify-center pt-3 flex-shrink-0"><div className="w-12 h-1.5 rounded-full" style={{ background: "#D1D5DB" }} /></div>
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 flex-shrink-0">
          <div>
            <h3 className="font-black text-gray-900" style={{ fontSize: "20px" }}>{(dateObj.getMonth() + 1)}월 {dateObj.getDate()}일</h3>
            <p className="text-gray-400 mt-0.5" style={{ fontSize: "14px" }}>{WD[wd]}요일{isHol ? " · 공휴일 🎌" : ""}{current ? " · 현재: " + current : ""}</p>
          </div>
          <button onClick={onClose} className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center text-gray-500 font-bold" style={{ fontSize: "20px" }}>×</button>
        </div>

        {confirm && (
          <div className="mx-4 my-3 rounded-2xl p-4 flex-shrink-0" style={{ background: "#FEF2F2", border: "1.5px solid #FECACA" }}>
            <p className="font-bold text-red-700 mb-2" style={{ fontSize: "15px" }}>⚠️ {confirm.shift} — 규칙 위반</p>
            {confirm.violations.map(function (v, i) { return <p key={i} className="text-red-500 mt-1" style={{ fontSize: "13px" }}>• {v}</p>; })}
            <div className="flex gap-2 mt-4">
              <button onClick={function () { setConfirm(null); }} className="flex-1 bg-white rounded-xl font-semibold" style={{ padding: "12px", fontSize: "14px", border: "1.5px solid #E5E7EB" }}>취소</button>
              <button onClick={function () { onSelect(confirm.shift); }} className="flex-1 bg-red-500 text-white rounded-xl font-bold" style={{ padding: "12px", fontSize: "14px" }}>무시하고 적용</button>
            </div>
          </div>
        )}

        <div className="px-4 py-3" style={{ flex: "1 1 0%", overflowY: "auto", WebkitOverflowScrolling: "touch", minHeight: 0 }}>
          {current && (
            <button onClick={function () { onSelect(""); onClose(); }} className="w-full mb-3 rounded-xl font-semibold text-gray-500" style={{ padding: "11px", fontSize: "15px", background: "#F3F4F6", border: "none" }}>
              ✕ 선택 초기화
            </button>
          )}
          {SHIFT_GROUPS.map(function (grp, gi) {
            var cols = 5;
            return (
              <div key={grp.label} style={{ marginBottom: gi < SHIFT_GROUPS.length - 1 ? "8px" : "0" }}>
                {gi > 0 && <div style={{ height: "1px", background: "#E5E7EB", margin: "8px 0 12px" }} />}
                <div className="flex items-center gap-2 mb-2.5">
                  <span className="rounded-full flex-shrink-0" style={{ width: "10px", height: "10px", background: grp.color }} />
                  <span className="font-bold" style={{ fontSize: "13px", color: grp.color }}>{grp.label}</span>
                  <span style={{ fontSize: "11px", color: "#9CA3AF" }}>{grp.shifts.length}종</span>
                </div>
                <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(" + cols + ", 1fr)" }}>
                  {grp.shifts.map(function (s) {
                    var ps = Object.assign({}, shifts); delete ps[day];
                    var vs = validate(ps, day, s, nurse, rules, startDate);
                    var isCur = s === current;
                    var st = sc(s);
                    return (
                      <button key={s} onClick={function () { handlePick(s); }}
                        className="relative rounded-xl font-bold transition-all active:scale-90"
                        style={{
                          padding: "11px 3px",
                          fontSize: "13px",
                          background: isCur ? st.fg : st.bg,
                          color: isCur ? "white" : st.fg,
                          border: "2px solid " + (isCur ? st.fg : vs.length > 0 ? "#FCA5A5" : st.border),
                          opacity: vs.length > 0 && !isCur ? 0.45 : 1,
                          boxShadow: isCur ? "0 2px 8px rgba(0,0,0,0.2)" : "none",
                        }}>
                        {s}
                        {vs.length > 0 && !isCur && <span className="absolute -top-1.5 -right-1.5 bg-red-500 rounded-full flex items-center justify-center text-white font-black" style={{ width: "16px", height: "16px", fontSize: "9px" }}>!</span>}
                        {isCur && <span className="absolute -top-1.5 -right-1.5 bg-blue-600 rounded-full flex items-center justify-center text-white font-black" style={{ width: "16px", height: "16px", fontSize: "9px" }}>✓</span>}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
          <div style={{ height: "env(safe-area-inset-bottom, 16px)", minHeight: "16px" }} />
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════
// PinModal — [버그1 수정] shared=true 명시 확인
// ══════════════════════════════════════════════
function PinModal(props) {
  var nurseId = props.nurseId, onClose = props.onClose;
  var [np, setNp] = useState(""), [cp, setCp] = useState(""), [err, setErr] = useState(""), [ok, setOk] = useState(false), [saving, setSaving] = useState(false);
  var handleSave = async function () {
    if (np.length < 4) { setErr("4자리 이상 입력해주세요."); return; }
    if (np !== cp) { setErr("PIN이 일치하지 않습니다."); return; }
    setSaving(true);
    try {
      // pins JSON 읽어서 해당 id만 업데이트 후 저장
      var allPins = {};
      var rp = await storageGet("pins", true);
      if (rp && rp.value) { try { allPins = JSON.parse(rp.value); } catch (e) { } }
      allPins[nurseId] = np;
      await storageSet("pins", JSON.stringify(allPins), true);
      setOk(true); setTimeout(onClose, 1500);
    } catch (e) {
      setErr("오류: " + e.message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6" onClick={function () { if (!saving) onClose(); }}>
      <div className="bg-white rounded-3xl shadow-2xl p-6 w-full max-w-xs" onClick={function (e) { e.stopPropagation(); }}>
        <h3 className="font-bold text-lg mb-1 text-center">🔐 PIN 변경</h3>
        <p className="text-xs text-gray-400 text-center mb-4">4~6자리 숫자</p>
        {ok ? (
          <div className="text-center py-6">
            <div className="text-5xl mb-3">✅</div>
            <p className="text-green-600 font-bold text-lg">변경 완료!</p>
            <p className="text-xs text-gray-400 mt-1">관리자 화면에도 즉시 반영됩니다</p>
          </div>
        ) : (
          <div className="space-y-3">
            <input type="password" inputMode="numeric" maxLength={6} value={np}
              onChange={function (e) { setNp(e.target.value.replace(/\D/g, "")); setErr(""); }}
              onKeyDown={function (e) { if (e.key === "Enter") handleSave(); }}
              placeholder="새 PIN" className={IC + " text-center text-xl tracking-widest"} />
            <input type="password" inputMode="numeric" maxLength={6} value={cp}
              onChange={function (e) { setCp(e.target.value.replace(/\D/g, "")); setErr(""); }}
              onKeyDown={function (e) { if (e.key === "Enter") handleSave(); }}
              placeholder="PIN 확인" className={IC + " text-center text-xl tracking-widest"} />
            {err && <p className="text-xs text-red-500 text-center bg-red-50 py-2 rounded-lg">{err}</p>}
            <div className="flex gap-2 pt-1">
              <button onClick={onClose} disabled={saving} className="flex-1 py-3 bg-gray-100 text-gray-600 rounded-xl font-semibold">취소</button>
              <button onClick={handleSave} disabled={saving || np.length < 4} className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-bold disabled:opacity-40">
                {saving ? "저장 중..." : "저장"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════
// AdminPage
// ══════════════════════════════════════════════
function AdminPage(props) {
  var nurses = props.nurses, saveNurses = props.saveNurses, rules = props.rules, saveRules = props.saveRules;
  var startDate = props.startDate, saveStartDate = props.saveStartDate, deadline = props.deadline, saveDeadline = props.saveDeadline, onBack = props.onBack;
  var [authed, setAuthed] = useState(false), [pw, setPw] = useState(""), [storedPw, setStoredPw] = useState("1234"), [tab, setTab] = useState("settings"), [pinKey, setPinKey] = useState(0), [showAdminPw, setShowAdminPw] = useState(false), [loginErr, setLoginErr] = useState("");

  useEffect(function () {
    (async function () {
      var r = await storageGet("admin_pw", true); if (r && r.value) setStoredPw(r.value);
    })();
  }, []);

  if (!authed) return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center p-6">
      <div className="w-full max-w-xs">
        <button onClick={onBack} className="text-gray-500 text-sm mb-6">← 돌아가기</button>
        <div className="bg-white rounded-3xl shadow-2xl overflow-hidden">
          <div className="bg-gray-900 px-6 py-5 text-center">
            <div className="text-3xl mb-2">🔐</div>
            <h2 className="text-xl font-bold text-white">관리자 로그인</h2>
            <p className="text-gray-500 text-xs mt-1">기본 비밀번호: 1234</p>
          </div>
          <div className="p-5">
            <input type="password" value={pw} onChange={function (e) { setPw(e.target.value); setLoginErr(""); }}
              onKeyDown={function (e) { if (e.key === "Enter") { if (pw === storedPw) setAuthed(true); else { setLoginErr("비밀번호가 틀렸습니다."); setPw(""); } } }}
              placeholder="비밀번호 입력" className={IC + " text-center text-xl tracking-widest mb-3"} />
            {loginErr && <div className="rounded-xl px-4 py-2.5 text-center font-medium mb-3" style={{ background: "#FEF2F2", color: "#DC2626", border: "1.5px solid #FECACA", fontSize: "14px" }}>{loginErr}</div>}
            <button onClick={function () { if (pw === storedPw) setAuthed(true); else { setLoginErr("비밀번호가 틀렸습니다."); setPw(""); } }}
              className="w-full py-3.5 bg-gray-900 text-white rounded-xl font-bold">로그인</button>
          </div>
        </div>
      </div>
    </div>
  );

  var tabs = [{ id: "settings", icon: "⚙️", label: "설정" }, { id: "nurses", icon: "👥", label: "간호사" }, { id: "pins", icon: "🔐", label: "PIN" }, { id: "submissions", icon: "📋", label: "신청현황" }];
  return (
    <div className="min-h-screen bg-gray-100" style={{ overflowX: "hidden" }}>
      <div className="sticky top-0 z-10 bg-white shadow-sm">
        <div className="flex items-center gap-3 px-4 pt-4 pb-3 border-b border-gray-100">
          <button onClick={onBack} className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center font-bold text-gray-600" style={{ fontSize: "16px" }}>←</button>
          <h1 className="font-black text-gray-900 flex-1" style={{ fontSize: "20px" }}>관리자</h1>
          <button onClick={function () { setShowAdminPw(true); }} className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center" style={{ fontSize: "18px" }} title="관리자 비밀번호 변경">🛡️</button>
        </div>
        <div className="flex overflow-x-auto" style={{ scrollbarWidth: "none" }}>
          {tabs.map(function (t) {
            return (
              <button key={t.id} onClick={function () { setTab(t.id); if (t.id === "pins") setPinKey(function (k) { return k + 1; }); }}
                className="flex-shrink-0 flex flex-col items-center transition-colors"
                style={{
                  padding: "10px 20px 8px",
                  borderBottom: tab === t.id ? "3px solid #2563EB" : "3px solid transparent",
                  color: tab === t.id ? "#2563EB" : "#6B7280",
                  background: tab === t.id ? "#EFF6FF" : "transparent",
                  fontWeight: tab === t.id ? 700 : 600,
                }}>
                <span style={{ fontSize: "18px" }}>{t.icon}</span>
                <span style={{ fontSize: "12px", marginTop: "2px" }}>{t.label}</span>
              </button>
            );
          })}
        </div>
      </div>
      <div className="p-4 overflow-hidden">
        {tab === "settings" && <SettingsTab startDate={startDate} saveStartDate={saveStartDate} deadline={deadline} saveDeadline={saveDeadline} rules={rules} saveRules={saveRules} />}
        {tab === "nurses" && <NurseManagement nurses={nurses} saveNurses={saveNurses} />}
        {tab === "pins" && <PinManagement nurses={nurses} key={pinKey} onVisible={function () { setPinKey(function (k) { return k + 1; }); }} />}
        {tab === "submissions" && <SubmissionsAdmin nurses={nurses} startDate={startDate} rules={rules} />}
      </div>
      {showAdminPw && <AdminPwModal storedPw={storedPw} setStoredPw={setStoredPw} onClose={function () { setShowAdminPw(false); }} />}
    </div>
  );
}

// ══════════════════════════════════════════════
// SettingsTab — 일정 + 규칙 통합
// ══════════════════════════════════════════════
function SettingsTab(props) {
  var saveStartDate = props.saveStartDate, saveDeadline = props.saveDeadline, saveRules = props.saveRules;
  var [sd, setSd] = useState(props.startDate || ""), [dl, setDl] = useState(props.deadline || ""), [scheduleSaved, setScheduleSaved] = useState(false), [scheduleErr, setScheduleErr] = useState("");
  var [r, setR] = useState(props.rules), [rulesSaved, setRulesSaved] = useState(false);
  var endDate = sd ? new Date(new Date(sd).getTime() + 27 * 86400000) : null;
  var passed = dlPassed(dl);
  var setVal = function (k, v) { setR(function (p) { var o = Object.assign({}, p); o[k] = v; return o; }); };
  var handleScheduleSave = async function () {
    if (!sd) { setScheduleErr("❌ 시작일을 선택해주세요"); setTimeout(function () { setScheduleErr(""); }, 3000); return; }
    setScheduleErr("");
    await saveStartDate(sd); await saveDeadline(dl || null);
    setScheduleSaved(true); setTimeout(function () { setScheduleSaved(false); }, 2500);
  };
  var fields = [
    ["max_consecutive_work", "최대 연속 근무", "일", "연속 근무 최대 일수"],
    ["max_consecutive_N", "최대 연속 야간", "개", "연속 N 최대 횟수"],
    ["off_after_2N", "NN 후 최소 휴무", "일", "야간 2연속 후 휴무일"],
    ["max_N_per_month", "월 최대 야간", "개", "한 달 N 상한"],
    ["min_weekly_off", "주당 최소 OFF", "일", "주 최소 휴무일"]
  ];
  return (
    <div className="space-y-4" style={{ maxWidth: "100%", overflowX: "hidden" }}>
      {/* ── 일정 섹션 ── */}
      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
          <p className="text-sm font-bold text-gray-700">📅 일정</p>
        </div>
        <div className="p-4 space-y-3 overflow-hidden">
          <div>
            <label className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1.5 block">근무표 시작일</label>
            <input type="date" value={sd} onChange={function (e) { setSd(e.target.value); setScheduleSaved(false); }} className={IC} style={{ maxWidth: "100%", boxSizing: "border-box" }} />
            {sd && endDate && <div className="mt-2 bg-blue-50 rounded-lg px-3 py-2 text-sm text-blue-700 font-medium">{fmtDate(sd)} ~ {fmtDate(endDate)} <span className="text-blue-400 text-xs">(28일)</span></div>}
          </div>
          <div>
            <label className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1.5 block">신청 마감일 <span className="text-gray-300 font-normal normal-case">(비워두면 마감 없음)</span></label>
            <input type="date" value={dl} onChange={function (e) { setDl(e.target.value); setScheduleSaved(false); }} className={IC} style={{ maxWidth: "100%", boxSizing: "border-box" }} />
            {dl && <div className={"mt-2 rounded-lg px-3 py-2 text-sm font-semibold " + (passed ? "bg-red-50 text-red-600" : "bg-yellow-50 text-yellow-700")}>{passed ? "⛔ 마감됨" : "⏰ " + fmtDate(dl) + " 자정까지"}</div>}
            {dl && <button onClick={function () { setDl(""); }} className="mt-1 text-xs text-gray-400 underline">마감일 제거</button>}
          </div>
        </div>
        {scheduleSaved && <p className="text-center text-xs text-green-600 font-semibold pb-3">✓ 저장되었습니다</p>}
        {scheduleErr && <p className="text-center text-xs text-red-600 font-semibold pb-3">{scheduleErr}</p>}
        <div className="px-4 pb-4">
          <button onClick={handleScheduleSave} className="w-full py-3 bg-blue-600 text-white rounded-xl font-bold text-sm">일정 저장</button>
        </div>
      </div>

      {/* ── 근무 규칙 섹션 ── */}
      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
          <p className="text-sm font-bold text-gray-700">⚙️ 근무 규칙</p>
        </div>
        {fields.map(function (f, i) {
          return (
            <div key={f[0]} className={"px-4 py-3 flex items-center justify-between " + (i < fields.length - 1 ? "border-b border-gray-100" : "")}>
              <div>
                <p className="text-sm font-semibold text-gray-900">{f[1]}</p>
                <p className="text-xs text-gray-400">{f[3]}</p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={function () { setVal(f[0], Math.max(0, (r[f[0]] || 0) - 1)); }} className="w-8 h-8 bg-gray-100 rounded-full text-gray-600 font-bold text-lg flex items-center justify-center">−</button>
                <span className="w-8 text-center font-bold text-gray-900 text-lg">{r[f[0]] || 0}</span>
                <button onClick={function () { setVal(f[0], (r[f[0]] || 0) + 1); }} className="w-8 h-8 bg-blue-600 rounded-full text-white font-bold text-lg flex items-center justify-center">+</button>
                <span className="text-xs text-gray-400 w-4">{f[2]}</span>
              </div>
            </div>
          );
        })}
        <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between">
          <div><p className="text-sm font-semibold text-gray-900">역순 금지</p><p className="text-xs text-gray-400">D→E→N 순서만 허용</p></div>
          <button onClick={function () { setVal("ban_reverse_order", !r.ban_reverse_order); }} className={"w-12 h-6 rounded-full transition-colors " + (r.ban_reverse_order ? "bg-blue-600" : "bg-gray-200")}>
            <span className={"block w-5 h-5 bg-white rounded-full shadow transition-transform mx-0.5 " + (r.ban_reverse_order ? "translate-x-6" : "translate-x-0")} />
          </button>
        </div>
        <div className="px-4 py-3 border-t border-gray-100">
          <p className="text-sm font-semibold text-gray-900 mb-1">법정공휴일</p>
          <p className="text-xs text-gray-400 mb-2">시작일 기준 몇째 날인지 쉼표로 구분</p>
          <input value={(r.public_holidays || []).join(", ")} placeholder="예: 1, 5, 15"
            onChange={function (e) { setVal("public_holidays", e.target.value.split(",").map(function (s) { return parseInt(s.trim()); }).filter(function (n) { return !isNaN(n) && n >= 1 && n <= 28; })); }}
            className={IC} />
        </div>
        {rulesSaved && <p className="text-center text-xs text-green-600 font-semibold pb-3">✓ 저장되었습니다</p>}
        <div className="px-4 pb-4 pt-2">
          <button onClick={async function () { await saveRules(r); setRulesSaved(true); setTimeout(function () { setRulesSaved(false); }, 2500); }} className="w-full py-3 bg-blue-600 text-white rounded-xl font-bold text-sm">규칙 저장</button>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════
// SubmissionsAdmin
// ══════════════════════════════════════════════
function SubmissionsAdmin(props) {
  var nurses = props.nurses, startDate = props.startDate, rules = props.rules;
  var [allData, setAllData] = useState({}), [loading, setLoading] = useState(false), [selectedDay, setSelectedDay] = useState(null), [showNames, setShowNames] = useState(false);

  var loadData = async function () {
    if (!startDate || nurses.length === 0) return;
    setLoading(true);
    // Promise.all 로 병렬 로드 (순차 대비 약 N배 빠름)
    var results = await Promise.all(nurses.map(function (n) {
      return storageGet("req:" + n.id + ":" + startDate, true).then(function (r) {
        return { id: n.id, name: n.name, data: r && r.value ? JSON.parse(r.value) : null };
      });
    }));
    var res = {};
    results.forEach(function (item) {
      if (item.data) res[item.id] = Object.assign({}, item.data, { nurseName: item.name });
    });
    setAllData(res); setLoading(false);
  };

  useEffect(function () {
    loadData();
  }, [nurses, startDate]);

  if (!startDate) return <div className="text-center py-16 text-gray-400"><p className="text-4xl mb-3">📅</p><p className="text-sm">시작일을 먼저 설정해주세요.</p></div>;
  if (loading) return <div className="text-center py-16 text-gray-400"><p className="text-2xl mb-2">⏳</p><p className="text-sm">불러오는 중...</p></div>;

  var dayMap = {};
  for (var d = 1; d <= NUM_DAYS; d++) dayMap[d] = { D: [], E: [], N: [], etc: [] };
  Object.values(allData).forEach(function (rec) {
    if (!rec.shifts) return;
    Object.entries(rec.shifts).forEach(function (e) {
      var day = +e[0], s = e[1]; if (!s) return;
      if (s === "D" || s === "D9" || s === "D1") dayMap[day].D.push(rec.nurseName);
      else if (s === "E") dayMap[day].E.push(rec.nurseName);
      else if (s === "N") dayMap[day].N.push(rec.nurseName);
      else if (s === "중2" || s === "중1") dayMap[day].D.push(rec.nurseName + "(중)");
      else dayMap[day].etc.push(rec.nurseName + "(" + s + ")");
    });
  });

  var submitted = nurses.filter(function (n) { return !!allData[n.id]; });
  var pending = nurses.filter(function (n) { return !allData[n.id]; });
  var startWd = getWd(startDate, 1);
  var cells = []; for (var ci = 0; ci < startWd; ci++) cells.push(null);
  for (var cd = 1; cd <= NUM_DAYS; cd++) cells.push(cd);
  while (cells.length % 7 !== 0) cells.push(null);

  var handleExport = function () {
    // ── 날짜 헤더 목록 구성 ──
    var endDate = new Date(new Date(startDate).getTime() + 27 * 86400000);
    var dateHeaders = [];
    for (var dd = 1; dd <= NUM_DAYS; dd++) {
      var dObj = getDate(startDate, dd);
      dateHeaders.push({
        day: dd,
        wd: getWd(startDate, dd),
        label: (dObj.getMonth() + 1) + "/" + dObj.getDate() + "(" + WD[getWd(startDate, dd)] + ")"
      });
    }

    // ── aoa 데이터 구성 ──
    var headerRow = ["이름", "역할", "직급"].concat(dateHeaders.map(function (h) { return h.label; })).concat(["제출일시"]);
    var aoa = [headerRow];
    // 각 셀의 스타일 정보를 별도 저장 (행,열 인덱스 기준)
    var styleMap = {}; // "R,C" → style object

    nurses.forEach(function (n, ri) {
      var rec = allData[n.id];
      var fixedWd = (n.fixed_weekly_off !== "" && n.fixed_weekly_off != null && !isNaN(parseInt(n.fixed_weekly_off))) ? parseInt(n.fixed_weekly_off) : -1;
      var row = [n.name, n.role || "", n.grade || ""];
      dateHeaders.forEach(function (dh, ci) {
        var shift = rec && rec.shifts && rec.shifts[dh.day] ? rec.shifts[dh.day] : "";
        var isFixed = (fixedWd >= 0 && dh.wd === fixedWd);
        if (!shift && isFixed) shift = "주";
        row.push(shift);
        var R = ri + 1, C = ci + 3;
        if (isFixed && !(rec && rec.shifts && rec.shifts[dh.day])) {
          // 고정주휴: 회색
          styleMap[R + "," + C] = { fill: { patternType: "solid", fgColor: { rgb: "C0C0C0" } }, font: { color: { rgb: "555555" } } };
        } else if (shift && shift !== "주") {
          // 신청 근무: 노란색
          styleMap[R + "," + C] = { fill: { patternType: "solid", fgColor: { rgb: "FFFF00" } }, font: { bold: true, color: { rgb: "000000" } } };
        }
      });
      row.push(rec && rec.submittedAt ? new Date(rec.submittedAt).toLocaleString("ko-KR") : "미제출");
      aoa.push(row);
    });

    var ws = XLSX.utils.aoa_to_sheet(aoa);

    // ── 스타일 적용 ──
    Object.keys(styleMap).forEach(function (key) {
      var parts = key.split(",");
      var addr = XLSX.utils.encode_cell({ r: parseInt(parts[0]), c: parseInt(parts[1]) });
      if (!ws[addr]) ws[addr] = { t: "s", v: "" };
      ws[addr].s = styleMap[key];
    });
    // 헤더 행 스타일
    for (var HC = 0; HC < headerRow.length; HC++) {
      var hAddr = XLSX.utils.encode_cell({ r: 0, c: HC });
      if (!ws[hAddr]) ws[hAddr] = { t: "s", v: "" };
      ws[hAddr].s = { fill: { patternType: "solid", fgColor: { rgb: "1D4ED8" } }, font: { color: { rgb: "FFFFFF" }, bold: true } };
    }

    // ── 열 너비 ──
    var colWidths = [{ wch: 8 }, { wch: 10 }, { wch: 8 }];
    for (var ci2 = 0; ci2 < NUM_DAYS; ci2++) colWidths.push({ wch: 5 });
    colWidths.push({ wch: 16 });
    ws["!cols"] = colWidths;

    var wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "신청현황");

    // 파일명: 근무신청_YYYYMMDD_YYYYMMDD.xlsx
    var sStr = startDate.replace(/-/g, "");
    var eStr = endDate.toISOString().slice(0, 10).replace(/-/g, "");
    XLSX.writeFile(wb, "근무신청_" + sStr + "_" + eStr + ".xlsx", { bookSST: false, cellStyles: true });
  };

  var selDetail = null;
  if (selectedDay) {
    var dm = dayMap[selectedDay];
    selDetail = {
      dateObj: getDate(startDate, selectedDay),
      wd: getWd(startDate, selectedDay),
      D: dm.D, E: dm.E, N: dm.N, etc: dm.etc,
      noReq: nurses.filter(function (n) { return !allData[n.id] || !(allData[n.id].shifts && allData[n.id].shifts[selectedDay]); }).map(function (n) { return n.name; })
    };
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs text-blue-700 bg-blue-50 rounded-xl px-3 py-2 font-medium">{fmtDate(startDate)} ~ {fmtDate(new Date(new Date(startDate).getTime() + 27 * 86400000))}</div>
        <div className="flex gap-2">
          <button onClick={loadData} className="px-3 py-2 bg-gray-100 text-gray-600 rounded-xl text-xs font-bold">🔄 새로고침</button>
          <button onClick={handleExport} className="px-3 py-2 bg-green-600 text-white rounded-xl text-xs font-bold flex items-center gap-1">📊 엑셀</button>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        <button onClick={function () { setShowNames(function (v) { return !v; }); }}
          className="w-full flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold text-green-600">제출 {submitted.length}명</span>
            <span className="text-gray-200">|</span>
            <span className="text-sm font-bold text-orange-500">미제출 {pending.length}명</span>
          </div>
          <span className="text-gray-400 text-xs">{showNames ? "▲" : "▼"}</span>
        </button>
        {showNames && (
          <div className="border-t border-gray-100 px-4 pb-3 pt-2 space-y-2">
            {submitted.length > 0 && <div><p className="text-xs font-bold text-green-600 mb-1">✅ 제출</p><p className="text-xs text-gray-600 leading-relaxed">{submitted.map(function (n) { return n.name; }).join(" · ")}</p></div>}
            {pending.length > 0 && <div><p className="text-xs font-bold text-orange-500 mb-1">⏳ 미제출</p><p className="text-xs text-gray-500 leading-relaxed">{pending.map(function (n) { return n.name; }).join(" · ")}</p></div>}
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <p className="text-sm font-bold text-gray-700">날짜별 신청 현황</p>
          <p className="text-xs text-gray-400">날짜 터치 → 상세</p>
        </div>
        <div className="grid grid-cols-7 bg-gray-50 border-b border-gray-100">
          {WD.map(function (wd, i) { return <div key={i} className={"text-center text-xs font-bold py-1.5 " + (i === 5 ? "text-blue-500" : i === 6 ? "text-red-500" : "text-gray-600")}>{wd}</div>; })}
        </div>
        <div className="grid grid-cols-7 gap-px bg-gray-100">
          {cells.map(function (day, i) {
            if (!day) return <div key={i} className="bg-white" />;
            var wd = getWd(startDate, day);
            var isSat = wd === 5, isSun = wd === 6;
            var isHol = (rules.public_holidays || []).includes(day);
            var dm = dayMap[day];
            var isSel = selectedDay === day;
            var dateObj = getDate(startDate, day);
            return (
              <button key={i} onClick={function () { setSelectedDay(function (prev) { return prev === day ? null : day; }); }}
                className={"bg-white flex flex-col items-center py-1.5 transition-colors " + (isSel ? "ring-2 ring-inset ring-blue-500 " : "") + (isSat || isSun || isHol ? "bg-blue-50/60" : "")}
                style={{ minHeight: "58px" }}>
                <span className={"font-semibold " + (isSat ? "text-blue-500" : isSun || isHol ? "text-red-500" : "text-gray-700")} style={{ fontSize: "9px" }}>{mmdd(dateObj)}</span>
                <div className="flex flex-col gap-0.5 mt-1 w-full px-0.5">
                  {dm.D.length > 0 && <div className="rounded text-white font-bold text-center" style={{ background: "#1D4ED8", fontSize: "7px", padding: "1px 0" }}>D {dm.D.length}</div>}
                  {dm.E.length > 0 && <div className="rounded text-white font-bold text-center" style={{ background: "#6D28D9", fontSize: "7px", padding: "1px 0" }}>E {dm.E.length}</div>}
                  {dm.N.length > 0 && <div className="rounded text-white font-bold text-center" style={{ background: "#B91C1C", fontSize: "7px", padding: "1px 0" }}>N {dm.N.length}</div>}
                  {dm.etc.length > 0 && <div className="rounded text-white font-bold text-center" style={{ background: "#D97706", fontSize: "7px", padding: "1px 0" }}>기 {dm.etc.length}</div>}
                  {(dm.D.length + dm.E.length + dm.N.length + dm.etc.length) === 0 && <div className="text-center text-gray-200" style={{ fontSize: "7px" }}>-</div>}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {selDetail && (
        <div className="bg-white rounded-2xl shadow-sm overflow-hidden border border-blue-200">
          <div className="bg-blue-600 px-4 py-3 flex items-center justify-between">
            <h3 className="font-bold text-white">{(selDetail.dateObj.getMonth() + 1)}월 {selDetail.dateObj.getDate()}일 ({WD[selDetail.wd]}) 상세</h3>
            <button onClick={function () { setSelectedDay(null); }} className="w-7 h-7 bg-white/20 rounded-full flex items-center justify-center text-white text-sm">×</button>
          </div>
          <div className="p-4 space-y-3">
            {[
              { label: "D (주간/중간)", names: selDetail.D, bg: "#EFF6FF", fg: "#1D4ED8" },
              { label: "E (저녁)", names: selDetail.E, bg: "#F5F3FF", fg: "#6D28D9" },
              { label: "N (야간)", names: selDetail.N, bg: "#FEF2F2", fg: "#B91C1C" },
              { label: "휴무/기타", names: selDetail.etc, bg: "#FFFBEB", fg: "#B45309" }
            ].map(function (row) {
              if (row.names.length === 0) return null;
              return (
                <div key={row.label}>
                  <p className="text-xs font-bold mb-1.5" style={{ color: row.fg }}>{row.label} · {row.names.length}명</p>
                  <div className="flex flex-wrap gap-1.5">
                    {row.names.map(function (nm, i2) { return <span key={i2} className="text-sm px-3 py-1.5 rounded-xl font-semibold border" style={{ background: row.bg, color: row.fg }}>{nm}</span>; })}
                  </div>
                </div>
              );
            })}
            {(selDetail.D.length + selDetail.E.length + selDetail.N.length + selDetail.etc.length) === 0 && <p className="text-sm text-gray-300 text-center py-2">신청 없음</p>}

          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════
// NurseManagement — [버그2 수정] normalizeNurse 적용
// ══════════════════════════════════════════════
function NurseManagement(props) {
  var nurses = props.nurses, saveNurses = props.saveNurses;
  var [form, setForm] = useState(null), [msg, setMsg] = useState(""), [confirmId, setConfirmId] = useState(null);
  var blank = { id: "", name: "", role: "", grade: "", is_pregnant: false, is_male: false, is_4day: false, fixed_weekly_off: "", vacation_days: 0 };

  var handleExcel = async function (e) {
    var file = e.target.files[0]; if (!file) return;
    try {
      var buf = await file.arrayBuffer();
      var wb = XLSX.read(buf, { type: "array" });
      var ws = wb.Sheets[wb.SheetNames[0]];
      var rows = XLSX.utils.sheet_to_json(ws, { defval: null, raw: true });
      var parsed = rows.filter(function (r) { return r["이름"] && String(r["이름"]).trim(); }).map(function (r, i) {
        // 비고3/비고4: "남자", "임산부", "주4일제" 텍스트값
        var b3 = String(r["비고3"] || "").trim();
        var b4 = String(r["비고4"] || "").trim();
        var allBigo = [b3, b4];
        var isMale = allBigo.includes("남자") || parseBool(r["남자"] || r["Male"] || r["남성"] || false);
        var isPreg = allBigo.includes("임산부") || parseBool(r["임산부"] || r["Pregnant"] || false);
        var is4day = allBigo.includes("주4일제") || parseBool(r["주4일제"] || r["4day"] || r["주4일"] || false);
        // 주휴/고정주휴/비고5 컬럼에서 요일 텍스트 → 인덱스
        var WD_MAP = { "월": "0", "화": "1", "수": "2", "목": "3", "금": "4", "토": "5", "일": "6" };
        var wdRaw = String(r["주휴"] || r["고정주휴"] || r["비고5"] || r["FixedOff"] || "").trim().replace(/요일$/, "");
        var fixedOff = WD_MAP[wdRaw] !== undefined ? WD_MAP[wdRaw] : (r["고정주휴"] != null && !isNaN(parseInt(r["고정주휴"])) ? String(parseInt(r["고정주휴"])) : "");
        return normalizeNurse({
          id: "n_" + Date.now() + "_" + i,
          name: String(r["이름"] || "").trim(),
          role: String(r["비고1"] || r["역할"] || r["Role"] || "").trim(),
          grade: String(r["비고2"] || r["직급"] || r["Grade"] || "").trim(),
          is_pregnant: isPreg,
          is_male: isMale,
          is_4day: is4day,
          fixed_weekly_off: fixedOff,
          vacation_days: parseInt(r["잔여연차"] || r["휴가잔여"] || r["Vacation"] || r["휴가"] || 0) || 0,
        });
      });
      await saveNurses(parsed);
      setMsg("✅ " + parsed.length + "명 등록 완료");
    } catch (err) { setMsg("❌ 파싱 실패: " + err.message); }
    e.target.value = ""; setTimeout(function () { setMsg(""); }, 4000);
  };

  var handleSave = async function (f) {
    var normalized = normalizeNurse(f);
    if (!normalized.id) normalized.id = "n_" + Date.now();
    var upd = f.id ? nurses.map(function (n) { return n.id === f.id ? normalized : n; }) : [].concat(nurses, [normalized]);
    await saveNurses(upd); setForm(null);
  };
  var handleDel = async function (id) { await saveNurses(nurses.filter(function (n) { return n.id !== id; })); setConfirmId(null); };

  return (
    <div className="space-y-3">
      <div className="bg-white rounded-2xl shadow-sm p-4">
        <div className="flex items-center justify-between mb-3">
          <div><h3 className="font-bold text-gray-900">간호사 목록</h3><p className="text-xs text-gray-400 mt-0.5">총 {nurses.length}명 등록됨</p></div>
          <div className="flex gap-2">
            <label className="px-3 py-2 bg-emerald-600 text-white rounded-xl text-xs font-bold cursor-pointer flex items-center gap-1">
              <span>📊</span> Excel<input type="file" accept=".xlsx,.xls" onChange={handleExcel} className="hidden" />
            </label>
            <button onClick={function () { setForm(Object.assign({}, blank)); }} className="px-3 py-2 bg-blue-600 text-white rounded-xl text-xs font-bold">+ 추가</button>
          </div>
        </div>
        {msg && <div className={"text-xs rounded-xl px-3 py-2 mb-3 " + (msg.startsWith("✅") ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700")}>{msg}</div>}
        <div className="bg-gray-50 rounded-xl px-3 py-2 text-xs text-gray-500 mb-3">
          Excel 컬럼: <b>이름</b> · 비고1(역할) · 비고2(직급) · 비고3(남자/임산부) · 비고4(주4일제) · 주휴(월~일) · 잔여연차
          <br /><span className="text-gray-400">체크값: 1, O, Y, v, T, ✓ 중 하나</span>
        </div>
        <div className="space-y-2">
          {nurses.map(function (n) {
            return (
              <div key={n.id} className="flex items-center gap-3 py-2.5 px-3 bg-gray-50 rounded-xl">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-bold text-gray-900">{n.name}</span>
                    {n.grade && <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-md font-medium">{n.grade}</span>}
                    {n.role && <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-md font-medium">{n.role}</span>}
                    {n.is_pregnant && <span className="text-xs">🤰</span>}
                    {n.is_male && <span className="text-xs text-blue-500 font-bold">♂</span>}
                    {n.is_4day && <span className="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-md">4일</span>}
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">
                    휴가 {n.vacation_days}일
                    {n.fixed_weekly_off !== "" && n.fixed_weekly_off != null && !isNaN(parseInt(n.fixed_weekly_off)) ? " · " + WD[parseInt(n.fixed_weekly_off)] + "요일 고정" : ""}
                  </p>
                </div>
                <div className="flex gap-1.5 flex-shrink-0">
                  <button onClick={function () { setForm(Object.assign({}, n)); }} className="px-2.5 py-1.5 bg-white border border-gray-200 text-gray-600 rounded-lg text-xs font-medium">수정</button>
                  <button onClick={function () { setConfirmId(n.id); }} className="px-2.5 py-1.5 bg-red-50 text-red-500 rounded-lg text-xs font-medium">삭제</button>
                </div>
              </div>
            );
          })}
          {nurses.length === 0 && <div className="text-center py-8 text-gray-300 text-sm">등록된 간호사가 없습니다.</div>}
        </div>
      </div>

      {confirmId && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6" onClick={function () { setConfirmId(null); }}>
          <div className="bg-white rounded-3xl shadow-2xl p-6 w-full max-w-xs text-center" onClick={function (e) { e.stopPropagation(); }}>
            <div className="text-4xl mb-3">🗑️</div>
            <h3 className="font-bold text-lg text-gray-900 mb-1">간호사 삭제</h3>
            <p className="text-sm text-gray-500 mb-5"><b className="text-gray-800">{(nurses.find(function (n) { return n.id === confirmId; }) || {}).name}</b>을(를) 삭제하시겠습니까?</p>
            <div className="flex gap-2">
              <button onClick={function () { setConfirmId(null); }} className="flex-1 py-3 bg-gray-100 text-gray-600 rounded-xl font-semibold">취소</button>
              <button onClick={function () { handleDel(confirmId); }} className="flex-1 py-3 bg-red-500 text-white rounded-xl font-bold">삭제</button>
            </div>
          </div>
        </div>
      )}
      {form && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-end" onClick={function () { setForm(null); }}>
          <div className="bg-white w-full rounded-t-3xl p-5 max-h-[90vh] overflow-y-auto" onClick={function (e) { e.stopPropagation(); }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-lg">{form.id ? "간호사 수정" : "간호사 추가"}</h3>
              <button onClick={function () { setForm(null); }} className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">×</button>
            </div>
            <div className="space-y-3">
              {[["이름 *", "name", "홍길동"], ["역할 (비고1)", "role", "책임만 / 중2 / 외상"], ["직급 (비고2)", "grade", "책임 / 서브차지"]].map(function (arr) {
                return (
                  <div key={arr[1]}>
                    <label className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1 block">{arr[0]}</label>
                    <input value={form[arr[1]] || ""} onChange={function (e) { var k = arr[1]; setForm(function (p) { var o = Object.assign({}, p); o[k] = e.target.value; return o; }); }} placeholder={arr[2]} className={IC} />
                  </div>
                );
              })}
              <div>
                <label className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1 block">휴가 잔여일</label>
                <input type="number" min="0" value={form.vacation_days || 0} onChange={function (e) { setForm(function (p) { return Object.assign({}, p, { vacation_days: +e.target.value }); }); }} className={IC} />
              </div>
              <div>
                <label className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1 block">고정 주휴</label>
                <select value={form.fixed_weekly_off || ""} onChange={function (e) { setForm(function (p) { return Object.assign({}, p, { fixed_weekly_off: e.target.value }); }); }} className={IC}>
                  <option value="">없음</option>
                  {WD.map(function (wd, i) { return <option key={i} value={String(i)}>{wd}요일</option>; })}
                </select>
              </div>
              <div className="bg-gray-50 rounded-xl p-3 flex gap-5 flex-wrap">
                {[["is_pregnant", "🤰 임산부"], ["is_male", "♂ 남성"], ["is_4day", "📅 주4일제"]].map(function (arr) {
                  return (
                    <label key={arr[0]} className="flex items-center gap-2 text-sm cursor-pointer font-medium text-gray-700">
                      <input type="checkbox" checked={!!form[arr[0]]}
                        onChange={function (e) { var k = arr[0]; setForm(function (p) { var o = Object.assign({}, p); o[k] = e.target.checked; return o; }); }}
                        className="w-4 h-4 accent-blue-600" />
                      {arr[1]}
                    </label>
                  );
                })}
              </div>
            </div>
            <div className="flex gap-2 mt-5">
              <button onClick={function () { setForm(null); }} className="flex-1 py-3.5 bg-gray-100 text-gray-600 rounded-2xl font-semibold">취소</button>
              <button onClick={function () { if ((form.name || "").trim()) handleSave(form); }} disabled={!(form.name || "").trim()} className="flex-1 py-3.5 bg-blue-600 text-white rounded-2xl font-bold disabled:opacity-30">저장</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════
// PinManagement — [버그1 수정] 새로고침 + 실시간 반영
// ══════════════════════════════════════════════
// PinManagement — pins 단일 JSON 키 사용
// ══════════════════════════════════════════════
function PinManagement(props) {
  var nurses = props.nurses;
  var [pins, setPins] = useState(null); // null=로딩중
  var [editId, setEditId] = useState(null);
  var [newPin, setNewPin] = useState("");
  var [msg, setMsg] = useState("");
  var [saving, setSaving] = useState(false);

  // pins JSON 한 번에 로드
  var loadPins = async function () {
    setPins(null);
    var allPins = {};
    var r = await storageGet("pins", true);
    if (r && r.value) {
      try { allPins = JSON.parse(r.value); } catch (e) { }
    }
    setPins(allPins);
  };

  useEffect(function () { loadPins(); }, [nurses]);

  // pins JSON 한 번에 저장하는 헬퍼
  var savePins = async function (updated) {
    setPins(updated); // 낙관적 UI 업데이트
    await storageSet("pins", JSON.stringify(updated), true);
  };

  var handleReset = async function (id) {
    var updated = Object.assign({}, pins || {});
    updated[id] = "0000";
    await savePins(updated);
    setMsg("✓ " + (nurses.find(function (n) { return n.id === id; }) || {}).name + " PIN 초기화");
    setTimeout(function () { setMsg(""); }, 2500);
  };

  var handleSet = async function () {
    if (!newPin || newPin.length < 4) { setMsg("❌ PIN은 4자리 이상"); setTimeout(function () { setMsg(""); }, 2000); return; }
    var id = editId;
    setSaving(true);
    try {
      var updated = Object.assign({}, pins || {});
      updated[id] = newPin;
      await savePins(updated);
      setMsg("✓ " + (nurses.find(function (n) { return n.id === id; }) || {}).name + " PIN 변경 완료");
      setEditId(null); setNewPin("");
    } catch (e) {
      setMsg("❌ 오류 발생");
    } finally {
      setSaving(false);
    }
    setTimeout(function () { setMsg(""); }, 3000);
  };

  if (pins === null) return <div className="text-center py-12 text-gray-400 text-sm">PIN 정보 불러오는 중…</div>;

  return (
    <div className="space-y-3">
      <div className="bg-amber-50 border border-amber-200 rounded-2xl px-4 py-3 text-sm text-amber-800">
        <b>초기 PIN: 0000</b> — 간호사가 직접 변경 가능합니다
      </div>
      <div className="flex justify-end">
        <button onClick={loadPins} className="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-xl text-xs font-bold">🔄 새로고침</button>
      </div>
      {msg && <div className={"text-sm rounded-xl px-4 py-2.5 font-medium " + (msg.startsWith("✓") ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700")}>{msg}</div>}
      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        {nurses.map(function (n, i) {
          return (
            <div key={n.id} className={"flex items-center gap-3 px-4 py-3.5 " + (i < nurses.length - 1 ? "border-b border-gray-100" : "")}>
              <div className="flex-1">
                <p className="font-bold text-gray-900">{n.name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <p className="text-xs text-gray-400">현재 PIN: <code className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-600">{(pins && pins[n.id]) || "0000"}</code></p>
                  {n.grade && <span className="text-xs bg-blue-100 text-blue-600 px-1.5 rounded">{n.grade}</span>}
                </div>
              </div>
              <button onClick={function () { setEditId(n.id); setNewPin(""); }} className="px-3 py-2 bg-blue-50 text-blue-600 rounded-xl text-xs font-bold">변경</button>
              <button onClick={function () { handleReset(n.id); }} className="px-3 py-2 bg-gray-100 text-gray-500 rounded-xl text-xs font-medium">초기화</button>
            </div>
          );
        })}
        {nurses.length === 0 && <div className="text-center py-8 text-gray-300 text-sm">간호사를 먼저 등록해주세요.</div>}
      </div>

      {editId && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6" onClick={function () { if (!saving) setEditId(null); }}>
          <div className="bg-white rounded-3xl shadow-2xl p-6 w-full max-w-xs" onClick={function (e) { e.stopPropagation(); }}>
            <h3 className="font-bold text-lg text-center mb-1">{(nurses.find(function (n) { return n.id === editId; }) || {}).name}</h3>
            <p className="text-xs text-gray-400 text-center mb-4">새 PIN 설정</p>
            <input type="password" inputMode="numeric" maxLength={6} value={newPin}
              onChange={function (e) { setNewPin(e.target.value.replace(/\D/g, "")); }}
              onKeyDown={function (e) { if (e.key === "Enter") handleSet(); }}
              placeholder="새 PIN (4~6자리 숫자)"
              className={IC + " text-center text-2xl tracking-widest mb-4"} />
            <div className="flex gap-2">
              <button onClick={function () { setEditId(null); }} disabled={saving} className="flex-1 py-3.5 bg-gray-100 text-gray-600 rounded-xl font-semibold">취소</button>
              <button onClick={handleSet} disabled={saving || newPin.length < 4} className="flex-1 py-3.5 bg-blue-600 text-white rounded-xl font-bold disabled:opacity-40">
                {saving ? "저장 중..." : "저장"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════
// AdminPwModal — 관리자 비밀번호 변경 모달
// ══════════════════════════════════════════════
function AdminPwModal(props) {
  var storedPw = props.storedPw, setStoredPw = props.setStoredPw, onClose = props.onClose;
  var [cur, setCur] = useState(""), [np, setNp] = useState(""), [cp, setCp] = useState(""), [msg, setMsg] = useState(""), [saving, setSaving] = useState(false), [ok, setOk] = useState(false);
  var handleSave = async function () {
    if (cur !== storedPw) { setMsg("❌ 현재 비밀번호 오류"); return; }
    if (np.length < 4) { setMsg("❌ 4자리 이상 입력"); return; }
    if (np !== cp) { setMsg("❌ 비밀번호 불일치"); return; }
    setSaving(true);
    var res = await storageSet("admin_pw", np, true);
    setSaving(false);
    if (res) { setStoredPw(np); setOk(true); setTimeout(onClose, 1500); }
    else setMsg("❌ 저장 실패");
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6" onClick={function () { if (!saving) onClose(); }}>
      <div className="bg-white rounded-3xl shadow-2xl p-6 w-full max-w-xs" onClick={function (e) { e.stopPropagation(); }}>
        <h3 className="font-bold text-lg mb-1 text-center">🛡️ 관리자 비밀번호</h3>
        <p className="text-xs text-gray-400 text-center mb-4">변경하려면 현재 비밀번호를 먼저 입력하세요</p>
        {ok ? (
          <div className="text-center py-6"><div className="text-5xl mb-3">✅</div><p className="text-green-600 font-bold text-lg">변경 완료!</p></div>
        ) : (
          <div className="space-y-3">
            <input type="password" value={cur} onChange={function (e) { setCur(e.target.value); setMsg(""); }} placeholder="현재 비밀번호" className={IC} />
            <input type="password" value={np} onChange={function (e) { setNp(e.target.value); setMsg(""); }} placeholder="새 비밀번호 (4자 이상)" className={IC} />
            <input type="password" value={cp} onChange={function (e) { setCp(e.target.value); setMsg(""); }} onKeyDown={function (e) { if (e.key === "Enter") handleSave(); }} placeholder="새 비밀번호 확인" className={IC} />
            {msg && <p className={"text-xs text-center py-2 rounded-lg font-medium " + (msg.startsWith("✓") ? "bg-green-50 text-green-600" : "bg-red-50 text-red-500")}>{msg}</p>}
            <div className="flex gap-2 pt-1">
              <button onClick={onClose} disabled={saving} className="flex-1 py-3 bg-gray-100 text-gray-600 rounded-xl font-semibold">취소</button>
              <button onClick={handleSave} disabled={saving || !cur || np.length < 4} className="flex-1 py-3 bg-gray-900 text-white rounded-xl font-bold disabled:opacity-40">{saving ? "저장 중..." : "변경하기"}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}