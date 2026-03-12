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
  "D":    { bg: "#EFF6FF", fg: "#1D4ED8", border: "#BFDBFE" },
  "D9":   { bg: "#EFF6FF", fg: "#1E40AF", border: "#BFDBFE" },
  "D1":   { bg: "#EFF6FF", fg: "#1E40AF", border: "#BFDBFE" },
  "E":    { bg: "#F5F3FF", fg: "#6D28D9", border: "#DDD6FE" },
  "N":    { bg: "#FEF2F2", fg: "#B91C1C", border: "#FECACA" },
  "중2":  { bg: "#ECFEFF", fg: "#0E7490", border: "#A5F3FC" },
  "중1":  { bg: "#ECFEFF", fg: "#155E75", border: "#A5F3FC" },
  "주":   { bg: "#FEFCE8", fg: "#854D0E", border: "#FEF08A" },
  "OFF":  { bg: "#F9FAFB", fg: "#374151", border: "#E5E7EB" },
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
  return dl ? new Date() > new Date(dl + "T23:59:59") : false;
}
