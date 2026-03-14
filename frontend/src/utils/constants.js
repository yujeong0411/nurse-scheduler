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
  { label: "기타", color: "#6B7280", shifts: ["보수", "필수", "번표", "D제외", "E제외", "N제외"] },
];

export const COLORS = {
  "D":    { bg: "#F8FAFF", fg: "#1D4ED8", border: "#DBEAFE" },
  "D9":   { bg: "#F8FAFF", fg: "#1E40AF", border: "#DBEAFE" },
  "D1":   { bg: "#F8FAFF", fg: "#1E40AF", border: "#DBEAFE" },
  "E":    { bg: "#FAF9FF", fg: "#6D28D9", border: "#EDE9FE" },
  "N":    { bg: "#FFF8F8", fg: "#B91C1C", border: "#FEE2E2" },
  "중2":  { bg: "#F7FEFF", fg: "#0E7490", border: "#CFFAFE" },
  "중1":  { bg: "#F7FEFF", fg: "#155E75", border: "#CFFAFE" },
  "주":   { bg: "#FFFEF5", fg: "#854D0E", border: "#FEF9C3" },
  "OFF":  { bg: "#F9FAFB", fg: "#374151", border: "#E5E7EB" },
  "POFF": { bg: "#F8FFF9", fg: "#166534", border: "#D1FAE5" },
  "법휴": { bg: "#FFFCF8", fg: "#9A3412", border: "#FED7AA" },
  "수면": { bg: "#F8F9FF", fg: "#3730A3", border: "#E0E7FF" },
  "생휴": { bg: "#FFF8FF", fg: "#86198F", border: "#FAE8FF" },
  "휴가": { bg: "#F8FFF9", fg: "#15803D", border: "#D1FAE5" },
  "병가": { bg: "#F8FAFC", fg: "#334155", border: "#E2E8F0" },
  "특휴": { bg: "#F8FFFD", fg: "#115E59", border: "#CCFBF1" },
  "공가": { bg: "#FAFFF5", fg: "#3F6212", border: "#ECFCCB" },
  "경가": { bg: "#FFFDF5", fg: "#78350F", border: "#FDE68A" },
  "보수": { bg: "#FAFAF9", fg: "#44403C", border: "#E7E5E4" },
  "필수": { bg: "#FFF8F9", fg: "#9F1239", border: "#FFE4E6" },
  "번표": { bg: "#FFF8FF", fg: "#701A75", border: "#FAE8FF" },
  "D제외": { bg: "#FFF8F8", fg: "#DC2626", border: "#FEE2E2" },
  "E제외": { bg: "#FAF9FF", fg: "#7C3AED", border: "#EDE9FE" },
  "N제외": { bg: "#FFF8F9", fg: "#BE123C", border: "#FFE4E6" },
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
