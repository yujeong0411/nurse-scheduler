// prototype request_app.jsx validate() 함수 그대로 이전
import { WORK_SET, SHIFT_ORDER, MID_D, N_NO_NEXT, NUM_DAYS, WD, getWd } from "./constants";

export function validate(shifts, day, s, nurse, rules, startDate) {
  if (!s) return [];
  var v = [];
  function g(d) { return shifts[d] || ""; }
  function dayStr(d) {
    if (!startDate) return d + "일";
    var dt = new Date(startDate); dt.setDate(dt.getDate() + d - 1);
    return (dt.getMonth() + 1) + "/" + dt.getDate();
  }
  var iw = WORK_SET.has(s);
  if (iw && rules.ban_reverse_order) {
    var p = g(day - 1), nx = g(day + 1);
    if (day > 1 && SHIFT_ORDER[p] && SHIFT_ORDER[s] && SHIFT_ORDER[p] > SHIFT_ORDER[s])
      v.push("역순 금지: " + dayStr(day - 1) + " " + p + "→" + dayStr(day) + " " + s);
    if (day < NUM_DAYS && SHIFT_ORDER[s] && SHIFT_ORDER[nx] && SHIFT_ORDER[s] > SHIFT_ORDER[nx])
      v.push("역순 금지: " + dayStr(day) + " " + s + "→" + dayStr(day + 1) + " " + nx);
  }
  if (iw) {
    var c = 1, dd = day - 1;
    while (dd >= 1 && WORK_SET.has(g(dd))) { c++; dd--; }
    dd = day + 1;
    while (dd <= NUM_DAYS && WORK_SET.has(g(dd))) { c++; dd++; }
    if (c > rules.max_consecutive_work) v.push("연속근무 " + c + "일 (최대 " + rules.max_consecutive_work + "일)");
    // NN/NNN 이상 블록 종료 후 off_after_2n일 내 근무 금지
    // 블록 끝이 day보다 off_after_2n일 이내에 있는지 확인
    for (var kb = 1; kb <= rules.off_after_2n; kb++) {
      var endPos = day - kb;
      if (endPos >= 2 && g(endPos) === "N" && g(endPos - 1) === "N"
          && (endPos + 1 >= day || g(endPos + 1) !== "N")) {
        // endPos는 N-블록의 끝, day는 그 블록 종료 후 kb일째
        v.push("N연속 후 " + kb + "일째 근무 금지 (최소 " + rules.off_after_2n + "일 휴무 필요)");
        break;
      }
    }
  }
  if (s === "N") {
    var cn = 1, dn = day - 1;
    while (dn >= 1 && g(dn) === "N") { cn++; dn--; }
    dn = day + 1;
    while (dn <= NUM_DAYS && g(dn) === "N") { cn++; dn++; }
    if (cn > rules.max_consecutive_n) v.push("연속 N " + cn + "개 (최대 " + rules.max_consecutive_n + "개)");
    var nc = Object.entries(shifts).filter(function(e) { return +e[0] !== day && e[1] === "N"; }).length + 1;
    if (nc > rules.max_n_per_month) v.push("월 N " + nc + "개 (최대 " + rules.max_n_per_month + "개)");
    // N 놓을 때: 블록 끝을 찾아 off_after_2n일 확인
    if (cn >= 2) {
      // 블록 끝 탐색
      var blkEnd = day;
      while (blkEnd < NUM_DAYS && g(blkEnd + 1) === "N") blkEnd++;
      for (var kn = 0; kn < rules.off_after_2n; kn++) {
        var c2 = blkEnd + 1 + kn;
        if (c2 <= NUM_DAYS && WORK_SET.has(g(c2))) {
          v.push("N" + cn + "연속 후 " + dayStr(c2) + " 근무 금지");
          break;
        }
      }
    }
  }
  if (MID_D.has(s) && day >= 3) {
    var p2 = g(day - 2), p1 = g(day - 1);
    if (p2 === "N" && p1 && !WORK_SET.has(p1)) v.push("N→1휴→" + s + " 금지");
  }
  if (s === "N" && day + 2 <= NUM_DAYS) {
    var n1 = g(day + 1), n2 = g(day + 2);
    if (n2 && MID_D.has(n2) && n1 && !WORK_SET.has(n1)) v.push("N→1휴→" + n2 + " 금지");
  }
  // N연속(≥2) 후 off_after_2n일 내 보수/필수/번표 금지 (backward: 블록 끝이어야 함)
  if (N_NO_NEXT.has(s)) {
    for (var ki = 1; ki <= rules.off_after_2n; ki++) {
      var nnEnd = day - ki;
      if (nnEnd >= 2 && g(nnEnd) === "N" && g(nnEnd - 1) === "N"
          && (nnEnd + 1 >= day || g(nnEnd + 1) !== "N")) {
        v.push("N연속 후 " + ki + "일째 " + s + " 금지"); break;
      }
    }
  }
  // N 놓을 때: 블록 끝 이후 off_after_2n일 내 보수/필수/번표 금지 (forward)
  if (s === "N" && cn >= 2) {
    for (var kf = 0; kf < rules.off_after_2n; kf++) {
      var fd = blkEnd + 1 + kf;
      if (fd <= NUM_DAYS && N_NO_NEXT.has(g(fd))) {
        v.push("N" + cn + "연속 후 " + kf + "일째 " + g(fd) + " 금지"); break;
      }
    }
  }
  if (s === "생휴") {
    if (nurse.is_male) v.push("생휴: 남성 불가");
    var targetMonth = startDate ? (function() { var dt = new Date(startDate); dt.setDate(dt.getDate() + day - 1); return dt.getMonth(); })() : null;
    var sameMonthGen = Object.entries(shifts).filter(function(e) {
      if (+e[0] === day || e[1] !== "생휴") return false;
      if (targetMonth === null) return true;
      var dt = new Date(startDate); dt.setDate(dt.getDate() + +e[0] - 1);
      return dt.getMonth() === targetMonth;
    }).length;
    if (sameMonthGen >= 1) v.push("생휴: 월 1회 초과");
  }
  if (s === "POFF" && !nurse.is_pregnant) v.push("POFF: 임산부만 가능");
  if (s === "중2") {
    if ((nurse.role || "").trim() !== "중2") v.push("중2: 역할 중2만 가능");
    if (startDate && [5, 6].indexOf(getWd(startDate, day)) >= 0) v.push("중2: 주말 불가");
  }
  if (s === "법휴" && !(rules.public_holidays || []).includes(day)) v.push("법휴: 공휴일 아님");
  if (s === "휴가") {
    var used = Object.entries(shifts).filter(function(e) { return +e[0] !== day && e[1] === "휴가"; }).length + 1;
    if (used > (nurse.vacation_days || 0)) v.push("휴가 잔여 초과");
  }
  if (nurse.fixed_weekly_off != null && nurse.fixed_weekly_off !== "" && startDate) {
    var fw = parseInt(nurse.fixed_weekly_off);
    if (!isNaN(fw) && getWd(startDate, day) === fw && s !== "주")
      v.push("고정주휴(" + WD[fw] + "): 주만 가능");
  }
  return v;
}
