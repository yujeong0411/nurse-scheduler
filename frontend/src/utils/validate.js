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
    // NN 후 off_after_2n일 내 근무 금지 (역방향: 근무를 놓을 때)
    for (var kb = 1; kb <= rules.off_after_2n; kb++) {
      var nnEndB = day - kb;
      if (nnEndB >= 2 && g(nnEndB) === "N" && g(nnEndB - 1) === "N") {
        v.push("NN 후 " + kb + "일째 근무 금지 (최소 " + rules.off_after_2n + "일 휴무 필요)");
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
    function chk(from) {
      for (var k = 0; k < rules.off_after_2n; k++) {
        var c2 = from + k;
        if (c2 <= NUM_DAYS && WORK_SET.has(g(c2))) { v.push("NN 후 " + dayStr(c2) + " 근무"); break; }
      }
    }
    if (day > 1 && g(day - 1) === "N") chk(day + 1);
    if (day < NUM_DAYS && g(day + 1) === "N") chk(day + 2);
  }
  if (MID_D.has(s) && day >= 3) {
    var p2 = g(day - 2), p1 = g(day - 1);
    if (p2 === "N" && p1 && !WORK_SET.has(p1)) v.push("N→1휴→" + s + " 금지");
  }
  if (s === "N" && day + 2 <= NUM_DAYS) {
    var n1 = g(day + 1), n2 = g(day + 2);
    if (n2 && MID_D.has(n2) && n1 && !WORK_SET.has(n1)) v.push("N→1휴→" + n2 + " 금지");
  }
  // NN 후 off_after_2n일 내 보수/필수/번표 금지 (backward: 현재 날짜가 해당 범위 내인지)
  if (N_NO_NEXT.has(s)) {
    for (var ki = 1; ki <= rules.off_after_2n; ki++) {
      var nnEnd = day - ki;
      if (nnEnd >= 2 && g(nnEnd) === "N" && g(nnEnd - 1) === "N") {
        v.push("NN 후 " + ki + "일째 " + s + " 금지"); break;
      }
    }
  }
  // NN 후 off_after_2n일 내 보수/필수/번표 금지 (forward: N을 놓을 때 이후 범위 확인)
  if (s === "N") {
    // 이전 N과 NN 형성 → day+1 ~ day+off_after_2n 확인
    if (day > 1 && g(day - 1) === "N") {
      for (var kf = 1; kf <= rules.off_after_2n; kf++) {
        var fd1 = day + kf;
        if (fd1 <= NUM_DAYS && N_NO_NEXT.has(g(fd1))) { v.push("NN 후 " + kf + "일째 " + g(fd1) + " 금지"); break; }
      }
    }
    // 다음 N과 NN 형성 → day+2 ~ day+1+off_after_2n 확인
    if (day < NUM_DAYS && g(day + 1) === "N") {
      for (var kf2 = 1; kf2 <= rules.off_after_2n; kf2++) {
        var fd2 = day + 1 + kf2;
        if (fd2 <= NUM_DAYS && N_NO_NEXT.has(g(fd2))) { v.push("NN 후 " + kf2 + "일째 " + g(fd2) + " 금지"); break; }
      }
    }
  }
  if (s === "생휴") {
    if (nurse.is_male) v.push("생휴: 남성 불가");
    if (Object.entries(shifts).filter(function(e) { return +e[0] !== day && e[1] === "생휴"; }).length >= 1)
      v.push("생휴: 월 1회 초과");
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
