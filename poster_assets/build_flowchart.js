const pptxgen = require("pptxgenjs");

const COLOR = {
  navy: "16233D",
  accent: "B3341F",
  muted: "5C574D",
  line: "D8D2C2",
  bg: "FBF9F3",
  white: "FFFFFF",
  cold: "33586B",
};
const FONT = "Malgun Gothic";

const pres = new pptxgen();
pres.defineLayout({ name: "FLOW", width: 13, height: 3.6 });
pres.layout = "FLOW";

const slide = pres.addSlide();
slide.background = { color: COLOR.white };

function box(x, y, w, h, { fill, line, textColor }, lines) {
  slide.addShape(pres.ShapeType.rect, {
    x, y, w, h,
    fill: { color: fill },
    line: { color: line, width: 1.25 },
  });
  slide.addText(
    lines.map((t, i) => ({
      text: t.text,
      options: {
        breakLine: i < lines.length - 1,
        fontSize: t.size,
        bold: t.bold || false,
        color: textColor,
      },
    })),
    {
      x: x + 0.05, y, w: w - 0.1, h,
      isTextBox: true, margin: 0,
      fontFace: FONT,
      align: "center", valign: "middle",
      lineSpacingMultiple: 1.05,
    }
  );
}

function arrow(x1, y1, x2, y2, color) {
  slide.addShape(pres.ShapeType.line, {
    x: Math.min(x1, x2), y: Math.min(y1, y2),
    w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
    line: { color, width: 1.5, endArrowType: "triangle" },
    flipV: y2 < y1,
  });
}

// ---- Main flow row ----
const rowY = 0.2;

box(0.15, rowY, 2.05, 0.85, { fill: COLOR.bg, line: COLOR.navy, textColor: COLOR.navy },
  [{ text: "원자료 수집", size: 12, bold: true }, { text: "충전소·생활인구·집계구 경계", size: 8.5 }]);

box(2.65, rowY, 2.55, 0.85, { fill: COLOR.bg, line: COLOR.navy, textColor: COLOR.navy },
  [{ text: "전처리·이동시간(OD) 산출", size: 12, bold: true }, { text: "운영시간 필터 + OD 계산", size: 8.5 }]);

box(5.65, rowY - 0.05, 3.05, 0.95, { fill: COLOR.accent, line: COLOR.accent, textColor: COLOR.white },
  [{ text: "Gaussian 2SFCA 접근성 모형", size: 12.5, bold: true },
   { text: "15분 컷오프 · 혼잡도 보통(30%) 적용", size: 8.5 }]);

box(9.15, rowY, 1.35, 0.85, { fill: COLOR.bg, line: COLOR.navy, textColor: COLOR.navy },
  [{ text: "결과 해석", size: 12, bold: true }]);

box(11.05, rowY + 0.13, 1.65, 0.6, { fill: COLOR.navy, line: COLOR.navy, textColor: COLOR.white },
  [{ text: "Gi* 공간통계", size: 12, bold: true }]);

const midY = rowY + 0.4;
arrow(2.2, midY, 2.6, midY, COLOR.navy);
arrow(5.2, midY, 5.6, midY, COLOR.navy);
arrow(8.7, midY, 9.1, midY, COLOR.navy);
arrow(10.5, midY, 11.0, midY, COLOR.navy);

// ---- Divider ----
slide.addShape(pres.ShapeType.line, {
  x: 0.15, y: 1.28, w: 12.7, h: 0,
  line: { color: COLOR.line, width: 1 },
});

// ---- Left mini panel: Gaussian decay curve ----
slide.addText("가우시안 감쇠함수 — 거리에 따른 접근성 가중치", {
  x: 0.15, y: 1.4, w: 5.9, h: 0.25, isTextBox: true, margin: 0,
  fontFace: FONT, fontSize: 11, bold: true, color: COLOR.muted,
});

const axL = { x: 0.75, yTop: 1.75, yBase: 2.95, xRight: 5.75 };
slide.addShape(pres.ShapeType.line, {
  x: axL.x, y: axL.yTop, w: 0, h: axL.yBase - axL.yTop,
  line: { color: COLOR.muted, width: 1 },
});
slide.addShape(pres.ShapeType.line, {
  x: axL.x, y: axL.yBase, w: axL.xRight - axL.x, h: 0,
  line: { color: COLOR.muted, width: 1 },
});

// Truncated-Gaussian decay: f(d) = [exp(-d^2/2b^2) - exp(-d0^2/2b^2)] / [1 - exp(-d0^2/2b^2)],
// normalized so f(0)=1 and f(d0)=0 exactly at the 15-minute cutoff (d0=15, b=5).
const cutX = 5.10; // x-position of d = 15 min (the cutoff)
const curvePts = [
  [0.75, 1.75],  // d=0   f=1.000
  [1.62, 1.95],  // d=3   f=0.833
  [2.49, 2.373], // d=6   f=0.4805
  [3.36, 2.724], // d=9   f=0.1887
  [4.23, 2.895], // d=12  f=0.0455
  [cutX, axL.yBase],  // d=15  f=0 (cutoff)
  [axL.xRight, axL.yBase], // flat zero beyond the cutoff
];
// NOTE: the smooth curve itself is NOT drawn here — pptxgenjs has no bezier/freeform
// shape support. It is spliced in afterward as a native <a:custGeom> cubic-bezier path
// by fix_curve.py, which reads curvePts below to compute matching control points.
// curvePts still doubles as the reference for that script's bounding box + anchor points.

slide.addShape(pres.ShapeType.line, {
  x: cutX, y: axL.yTop, w: 0, h: axL.yBase - axL.yTop,
  line: { color: COLOR.navy, width: 1, dashType: "dash" },
});
slide.addText("15분 컷오프", {
  x: cutX - 1.35, y: axL.yTop + 0.02, w: 1.3, h: 0.22, isTextBox: true, margin: 0,
  fontFace: FONT, fontSize: 8.5, bold: true, color: COLOR.navy, align: "right",
});
slide.addText("이후 f(d)=0", {
  x: cutX + 0.05, y: 2.55, w: 1.15, h: 0.2, isTextBox: true, margin: 0,
  fontFace: FONT, fontSize: 6.5, italic: true, color: COLOR.muted,
});
slide.addText("0", {
  x: axL.x - 0.1, y: axL.yBase + 0.02, w: 0.3, h: 0.18, isTextBox: true, margin: 0,
  fontFace: FONT, fontSize: 7, color: COLOR.muted,
});
slide.addText("15(분)", {
  x: cutX - 0.35, y: axL.yBase + 0.02, w: 0.7, h: 0.18, isTextBox: true, margin: 0,
  fontFace: FONT, fontSize: 7, bold: true, color: COLOR.navy, align: "center",
});
slide.addText("가중치", {
  x: 0.05, y: 2.15, w: 0.7, h: 0.3, isTextBox: true, margin: 0,
  fontFace: FONT, fontSize: 8, color: COLOR.muted, align: "center",
  rotate: 270,
});

// ---- Right mini panel: Gi* concept ----
slide.addText("Getis-Ord Gi* — 국지적 클러스터링 개념", {
  x: 6.35, y: 1.4, w: 6.4, h: 0.25, isTextBox: true, margin: 0,
  fontFace: FONT, fontSize: 11, bold: true, color: COLOR.muted,
});

const gridColors = [
  [COLOR.accent, COLOR.accent, COLOR.line],
  [COLOR.line, COLOR.line, COLOR.cold],
  [COLOR.line, COLOR.cold, COLOR.cold],
];
const gx = [6.5, 7.1, 7.7];
const gy = [1.78, 2.28, 2.78];
for (let r = 0; r < 3; r++) {
  for (let c = 0; c < 3; c++) {
    slide.addShape(pres.ShapeType.ellipse, {
      x: gx[c], y: gy[r], w: 0.42, h: 0.42,
      fill: { color: gridColors[r][c] },
      line: { type: "none" },
    });
  }
}

const legend = [
  { color: COLOR.accent, text: "핫스팟(유의 상위 군집)" },
  { color: COLOR.cold, text: "콜드스팟(유의 하위 군집)" },
  { color: COLOR.line, text: "유의하지 않음" },
];
legend.forEach((item, i) => {
  const ly = 1.8 + i * 0.5;
  slide.addShape(pres.ShapeType.ellipse, {
    x: 8.9, y: ly, w: 0.26, h: 0.26,
    fill: { color: item.color },
    line: { type: "none" },
  });
  slide.addText(item.text, {
    x: 9.3, y: ly - 0.03, w: 3.5, h: 0.32, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 9.5, color: COLOR.muted, valign: "middle",
  });
});

// ---- Caption ----
slide.addText(
  "그림0 — Data and Methods 흐름도: 원자료→전처리·이동시간(OD) 산출→Gaussian 2SFCA(15분 컷오프·혼잡도 보통 30%)→결과 해석→Gi* 공간통계. 하단: 가우시안 감쇠함수, Gi* 클러스터링 개념",
  {
    x: 0.15, y: 3.25, w: 12.7, h: 0.3, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 8, italic: true, color: COLOR.muted,
  }
);

pres.writeFile({ fileName: "MM_flowchart_v1.pptx" }).then(() => {
  console.log("done");
});
