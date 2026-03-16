// prototype request_app.jsx에서 이전
export const NUM_DAYS = 28;
export const WD = ["월", "화", "수", "목", "금", "토", "일"];
export const WORK_SET = new Set(["D", "D9", "D1", "중1", "중2", "E", "N"]);
export const SHIFT_ORDER = { "D": 1, "D9": 2, "D1": 2, "중1": 2, "중2": 2, "E": 3, "N": 4 };
export const MID_D = new Set(["D", "D9", "D1", "중1", "중2"]);
export const N_NO_NEXT = new Set(["보수", "필수", "번표"]);

export const DEFAULT_RULES = {
  max_consecutive_work: 5,
  max_consecutive_n: 3,
  off_after_2n: 2,
  max_n_per_month: 6,
  min_weekly_off: 2,
  ban_reverse_order: true,
  public_holidays: [],
};

export const SHIFT_GROUPS = [
  { label: "근무", color: "#2563EB", shifts: ["D", "D9", "D1", "중2", "중1", "E", "N"] },
  { label: "휴무", color: "#D97706", shifts: ["OFF", "POFF", "법휴", "수면", "생휴", "휴가", "병가", "특휴", "공가", "경가"] },
  { label: "기타", color: "#6B7280", shifts: ["보수", "필수", "번표", "D 제외", "E 제외", "N 제외"] },
];

// 공통 팔레트
const GRAY = { bg: "#F4F5F7", fg: "#4B5563", border: "#9CA3AF" };  // 휴무/기타
const EXCL = { bg: "#FFF7ED", fg: "#C2410C", border: "#FDBA74" };  // 제외 (오렌지)

export const COLORS = {
  // 근무
  "D":    { bg: "#F0FDF4", fg: "#15803D", border: "#86EFAC" },  // 초록
  "D9":   { bg: "#F0F9FF", fg: "#0369A1", border: "#7DD3FC" },  // 하늘
  "D1":   { bg: "#F0F9FF", fg: "#0369A1", border: "#7DD3FC" },
  "중2":  { bg: "#F0F9FF", fg: "#0369A1", border: "#7DD3FC" },
  "중1":  { bg: "#F0F9FF", fg: "#0369A1", border: "#7DD3FC" },
  "E":    { bg: "#FAF5FF", fg: "#7E22CE", border: "#C4B5FD" },  // 보라
  "N":    { bg: "#FFF1F2", fg: "#BE123C", border: "#FCA5A5" },  // 빨강
  // 휴무 10종
  "주":   { bg: "#FFFEF5", fg: "#854D0E", border: "#FEF9C3" },  // 주휴는 유지
  "OFF":  GRAY,
  "POFF": GRAY,
  "법휴": GRAY,
  "수면": GRAY,
  "생휴": GRAY,
  "휴가": GRAY,
  "병가": GRAY,
  "특휴": GRAY,
  "공가": GRAY,
  "경가": GRAY,
  // 기타
  "보수": GRAY,
  "필수": GRAY,
  "번표": GRAY,
  // 제외
  "D 제외": EXCL,
  "E 제외": EXCL,
  "N 제외": EXCL,
};

export function sc(s) {
  return COLORS[s] || { bg: "#F9FAFB", fg: "#9CA3AF", border: "#E5E7EB" };
}

export function fmtDate(d) {
  if (!d) return "";
  var dt = typeof d === "string" ? new Date(d) : d;
  return dt.getFullYear() + "." + String(dt.getMonth() + 1).padStart(2, "0") + "." + String(dt.getDate()).padStart(2, "0");
}

export function getWd(sd, idx) {
  var d = new Date(sd); d.setDate(d.getDate() + idx - 1); return (d.getDay() + 6) % 7;
}

export function getDate(sd, idx) {
  var d = new Date(sd); d.setDate(d.getDate() + idx - 1); return d;
}

export function mmdd(d) {
  return (d.getMonth() + 1) + "/" + d.getDate();
}

export function dlPassed(dl) {
  if (!dl) return false
  // "YYYY-MM-DDTHH:MM" 형식이면 그대로, "YYYY-MM-DD" 형식이면 자정으로
  const dt = dl.includes('T') ? new Date(dl) : new Date(dl + 'T23:59:59')
  return new Date() > dt
}
