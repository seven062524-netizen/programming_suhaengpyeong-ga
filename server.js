
const express = require("express");
require("dotenv").config();

const app = express();
const PORT = 3000;
const MODEL = "gemini-3.1-flash-lite";

app.use(express.json({ limit: "1mb" }));
app.use(express.static(__dirname));
// URL의 추적용 매개변수 자동 제거
app.use((req, res, next) => {
    const url = new URL(req.originalUrl, "http://localhost");

    if (url.searchParams.has("utm_source")) {
        url.searchParams.delete("utm_source");

        const query = url.searchParams.toString();
        const cleanUrl = url.pathname + (query ? `?${query}` : "");

        return res.redirect(302, cleanUrl);
    }

    next();
});

let ai;

// 기능별 Gemini 프롬프트
const modePrompts = {
    diagnosis: (content) => `
너는 학생들의 프롬프트를 분석하는 AI 전문가야.

아래 프롬프트를 한국어로 분석해 줘.

[분석할 프롬프트]
${content}

다음 항목을 중심으로 설명해 줘.
1. 목적이 명확한가?
2. 조건과 상황 설명이 충분한가?
3. 원하는 결과물의 형식이 구체적인가?
4. 모호하거나 빠진 표현은 무엇인가?
5. 어떻게 개선하면 좋은가?

잘한 점도 함께 짚고, 마지막에 개선된 프롬프트 예시를 제시해 줘.
학생이 이해하기 쉬운 표현을 사용해 줘.
`,

    error: (content, code) => `
너는 프로그래밍 및 AI 오류 분석 전문가야.

다음 오류를 한국어로 분석해 줘.

[오류 메시지]
${content}

[관련 코드 또는 추가 상황]
${code || "추가 정보 없음"}

다음 순서로 설명해 줘.
1. 오류의 의미
2. 가능한 원인
3. 해결 방법
4. 수정할 때 주의할 점

확실하지 않은 내용은 가능성이라고 밝혀 줘.
코드나 상황 정보가 부족하면 무엇이 더 필요한지도 알려 줘.
`,

    improve: (content) => `
너는 프롬프트 개선 전문가야.

다음 프롬프트의 원래 의도는 유지하면서 더 명확하고 구체적으로 개선해 줘.

[기존 프롬프트]
${content}

먼저 복사해서 사용할 수 있는 개선된 프롬프트를 제시해 줘.
그다음 역할, 목적, 조건, 출력 형식 중 무엇을 어떻게 개선했는지 설명해 줘.
사용자가 말하지 않은 사실이나 조건을 임의로 확정하지 마.
`,

    practice: (content) => `
너는 학생의 프롬프트 작성 연습을 도와주는 선생님이야.

아래 프롬프트를 평가해 줘.

[학생의 프롬프트]
${content}

다음 항목을 중심으로 피드백해 줘.
1. 목적의 명확성
2. 조건의 구체성
3. 결과 형식의 명확성
4. 모호한 표현
5. 잘한 점과 개선할 점

마지막에는 학생이 직접 수정해 볼 수 있는 구체적인 조언을 줘.
정답만 제시하지 말고 왜 개선해야 하는지도 설명해 줘.
`
};

// 서버 상태 확인
app.get("/api/status", (req, res) => {
    res.json({
        success: true,
        model: MODEL,
        message: "Prompt Doctor 서버가 실행 중입니다."
    });
});

// Gemini 분석 요청
app.post("/api/analyze", async (req, res) => {
    try {
        const { mode, content, code } = req.body || {};

        if (typeof content !== "string" || !content.trim()) {
            return res.status(400).json({
                success: false,
                error: "분석할 내용을 입력해 주세요."
            });
        }

        if (content.length > 5000) {
            return res.status(400).json({
                success: false,
                error: "입력 내용은 5,000자 이하로 작성해 주세요."
            });
        }

        if (!Object.prototype.hasOwnProperty.call(modePrompts, mode)) {
            return res.status(400).json({
                success: false,
                error: "지원하지 않는 분석 기능입니다."
            });
        }

        const prompt = modePrompts[mode](content, code || "");

        const response = await ai.models.generateContent({
            model: MODEL,
            contents: prompt
        });

        const resultText = response.text;

        if (!resultText) {
            throw new Error("Gemini에서 분석 결과를 반환하지 않았습니다.");
        }

        res.json({
            success: true,
            result: resultText
        });

    } catch (error) {
        console.error("Gemini API 오류:", error);

        res.status(500).json({
            success: false,
            error: "Gemini 분석에 실패했습니다: " +
                (error.message || "알 수 없는 오류")
        });
    }
});

// 서버 실행
async function startServer() {
    if (!process.env.GEMINI_API_KEY) {
        console.error(
            "오류: .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다."
        );
        process.exit(1);
    }

    const { GoogleGenAI } = await import("@google/genai");

    ai = new GoogleGenAI({
        apiKey: process.env.GEMINI_API_KEY
    });

    app.listen(PORT, () => {
        console.log("------------------------------------");
        console.log("Prompt Doctor 서버 실행 중!");
        console.log(`주소: http://localhost:${PORT}`);
        console.log(`모델: ${MODEL}`);
        console.log("------------------------------------");
    });
}

startServer().catch((error) => {
    console.error("서버 시작 실패:", error);
    process.exit(1);
});
