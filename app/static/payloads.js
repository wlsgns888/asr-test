window.createConversionJobPayload = function createConversionJobPayload(
  uploadId,
  speakerSeparationEnabled,
) {
  return {
    speaker_separation_enabled: speakerSeparationEnabled,
    upload_id: uploadId,
  };
};

window.createMinutesPayload = function createMinutesPayload(
  transcriptId,
  template,
  summaryPrompt,
) {
  const payload = {
    template,
    transcript_id: transcriptId,
  };
  const prompt = summaryPrompt.trim();
  if (prompt) {
    payload.summary_prompt = prompt;
  }
  return payload;
};

window.parseJsonResponse = function parseJsonResponse(text) {
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
};
