export interface AppConfig {
  pageTitle: string;
  pageDescription: string;
  companyName: string;

  supportsChatInput: boolean;
  supportsVideoInput: boolean;
  supportsScreenShare: boolean;
  isPreConnectBufferEnabled: boolean;

  logo: string;
  startButtonText: string;
  accent?: string;
  logoDark?: string;
  accentDark?: string;

  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorDark?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;

  // agent dispatch configuration
  agentName?: string;

  // LiveKit Cloud Sandbox configuration
  sandboxId?: string;
}

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'UATU',
  pageTitle: 'UATU — Generative AI Query & Voice Command Interface',
  pageDescription: 'On-Premise Evidence-Grounded Video Intelligence • English & Tamil/Tanglish',

  supportsChatInput: true,
  supportsVideoInput: true,
  supportsScreenShare: true,
  isPreConnectBufferEnabled: true,

  logo: '/lk-logo.svg',
  accent: '#10b981',
  logoDark: '/lk-logo-dark.svg',
  accentDark: '#10b981',
  startButtonText: 'Connect to UATU Voice AI',

  // optional: audio visualization configuration
  audioVisualizerColor: '#10b981',
  audioVisualizerColorDark: '#10b981',
  audioVisualizerType: 'aura',

  // agent dispatch configuration
  agentName: process.env.AGENT_NAME || 'iris',

  // LiveKit Cloud Sandbox configuration
  sandboxId: undefined,
};
