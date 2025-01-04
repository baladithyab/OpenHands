export const LATEST_SETTINGS_VERSION = 6;

export type Settings = {
  LLM_MODEL: string;
  LLM_BASE_URL: string;
  AGENT: string;
  LANGUAGE: string;
  LLM_API_KEY: string | null;
  CONFIRMATION_MODE: boolean;
  SECURITY_ANALYZER: string;
  // AWS Bedrock settings
  AWS_ACCESS_KEY_ID?: string;
  AWS_SECRET_ACCESS_KEY?: string;
  AWS_SESSION_TOKEN?: string;
  AWS_REGION_NAME?: string;
  AWS_PROFILE_NAME?: string;
  AWS_ROLE_NAME?: string;
  AWS_SESSION_NAME?: string;
  AWS_WEB_IDENTITY_TOKEN?: string;
  AWS_BEDROCK_ENDPOINT?: string;
  // Bedrock guardrails
  BEDROCK_ENABLE_GUARDRAILS?: boolean;
  BEDROCK_GUARDRAIL_ID?: string;
  BEDROCK_GUARDRAIL_VERSION?: string;
  BEDROCK_GUARDRAIL_TRACE?: boolean;
  // Bedrock cross-region
  BEDROCK_ENABLE_CROSS_REGION?: boolean;
  BEDROCK_CROSS_REGION_TARGET?: string;
  // Prompt caching
  enable_caching?: boolean;
  cache_ttl_seconds?: number;
  cache_min_tokens?: number | null;
  cache_max_checkpoints?: number | null;
  cache_strategy?: string;
  // Prompt routing
  enable_routing?: boolean;
  routing_strategy?: string;
  routing_model_family?: string;
  routing_cross_region?: boolean;
  routing_metrics_enabled?: boolean;
};

export type ApiSettings = {
  llm_model: string;
  llm_base_url: string;
  agent: string;
  language: string;
  llm_api_key: string | null;
  confirmation_mode: boolean;
  security_analyzer: string;
  // AWS Bedrock settings
  aws_access_key_id?: string;
  aws_secret_access_key?: string;
  aws_session_token?: string;
  aws_region_name?: string;
  aws_profile_name?: string;
  aws_role_name?: string;
  aws_session_name?: string;
  aws_web_identity_token?: string;
  aws_bedrock_endpoint?: string;
  // Bedrock guardrails
  bedrock_enable_guardrails?: boolean;
  bedrock_guardrail_id?: string;
  bedrock_guardrail_version?: string;
  bedrock_guardrail_trace?: boolean;
  // Bedrock cross-region
  bedrock_enable_cross_region?: boolean;
  bedrock_cross_region_target?: string;
  // Prompt caching
  enable_caching?: boolean;
  cache_ttl_seconds?: number;
  cache_min_tokens?: number | null;
  cache_max_checkpoints?: number | null;
  cache_strategy?: string;
  // Prompt routing
  enable_routing?: boolean;
  routing_strategy?: string;
  routing_model_family?: string;
  routing_cross_region?: boolean;
  routing_metrics_enabled?: boolean;
};

export const DEFAULT_SETTINGS: Settings = {
  LLM_MODEL: "anthropic/claude-3-5-sonnet-20241022",
  LLM_BASE_URL: "",
  AGENT: "CodeActAgent",
  LANGUAGE: "en",
  LLM_API_KEY: null,
  CONFIRMATION_MODE: false,
  SECURITY_ANALYZER: "",
  // AWS Bedrock settings
  AWS_ACCESS_KEY_ID: undefined,
  AWS_SECRET_ACCESS_KEY: undefined,
  AWS_SESSION_TOKEN: undefined,
  AWS_REGION_NAME: undefined,
  AWS_PROFILE_NAME: undefined,
  AWS_ROLE_NAME: undefined,
  AWS_SESSION_NAME: undefined,
  AWS_WEB_IDENTITY_TOKEN: undefined,
  AWS_BEDROCK_ENDPOINT: undefined,
  // Bedrock guardrails
  BEDROCK_ENABLE_GUARDRAILS: false,
  BEDROCK_GUARDRAIL_ID: undefined,
  BEDROCK_GUARDRAIL_VERSION: undefined,
  BEDROCK_GUARDRAIL_TRACE: false,
  // Bedrock cross-region
  BEDROCK_ENABLE_CROSS_REGION: false,
  BEDROCK_CROSS_REGION_TARGET: undefined,
  // Prompt caching
  enable_caching: false,
  cache_ttl_seconds: 3600,
  cache_min_tokens: null,
  cache_max_checkpoints: null,
  cache_strategy: 'default',
  // Prompt routing
  enable_routing: false,
  routing_strategy: 'balanced',
  routing_model_family: 'auto',
  routing_cross_region: false,
  routing_metrics_enabled: false,
};

export const getCurrentSettingsVersion = () => {
  const settingsVersion = localStorage.getItem("SETTINGS_VERSION");
  if (!settingsVersion) return 0;
  try {
    return parseInt(settingsVersion, 10);
  } catch (e) {
    return 0;
  }
};

export const settingsAreUpToDate = () =>
  getCurrentSettingsVersion() === LATEST_SETTINGS_VERSION;

// TODO: localStorage settings are deprecated. Remove this after 1/31/2025
/**
 * Get the settings from local storage
 * @returns the settings from local storage
 * @deprecated
 */
export const getLocalStorageSettings = (): Settings => {
  const llmModel = localStorage.getItem("LLM_MODEL");
  const baseUrl = localStorage.getItem("LLM_BASE_URL");
  const agent = localStorage.getItem("AGENT");
  const language = localStorage.getItem("LANGUAGE");
  const llmApiKey = localStorage.getItem("LLM_API_KEY");
  const confirmationMode = localStorage.getItem("CONFIRMATION_MODE") === "true";
  const securityAnalyzer = localStorage.getItem("SECURITY_ANALYZER");

  return {
    LLM_MODEL: llmModel || DEFAULT_SETTINGS.LLM_MODEL,
    LLM_BASE_URL: baseUrl || DEFAULT_SETTINGS.LLM_BASE_URL,
    AGENT: agent || DEFAULT_SETTINGS.AGENT,
    LANGUAGE: language || DEFAULT_SETTINGS.LANGUAGE,
    LLM_API_KEY: llmApiKey || DEFAULT_SETTINGS.LLM_API_KEY,
    CONFIRMATION_MODE: confirmationMode || DEFAULT_SETTINGS.CONFIRMATION_MODE,
    SECURITY_ANALYZER: securityAnalyzer || DEFAULT_SETTINGS.SECURITY_ANALYZER,
  };
};

/**
 * Get the default settings
 */
export const getDefaultSettings = (): Settings => DEFAULT_SETTINGS;
