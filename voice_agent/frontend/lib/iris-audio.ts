/** Browser-side capture processing; this does not alter the assistant's voice. */
export const VOICE_CAPTURE_DEFAULTS = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
  channelCount: 1,
} as const;
