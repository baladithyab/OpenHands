import React from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";

interface PromptCachingInputsProps {
  isDisabled?: boolean;
  defaultValues?: {
    enableCaching?: boolean;
    cacheTtlSeconds?: number;
    cacheMinTokens?: number | null;
    cacheMaxCheckpoints?: number | null;
    cacheStrategy?: string;
  };
  modelId?: string;  // To determine model-specific defaults
}

export function PromptCachingInputs({
  isDisabled,
  defaultValues = {},
  modelId,
}: PromptCachingInputsProps) {
  const { t } = useTranslation();
  const [enableCaching, setEnableCaching] = React.useState(defaultValues.enableCaching ?? true);

  // Get model-specific defaults
  const getModelDefaults = (modelId: string | undefined) => {
    if (!modelId) return { minTokens: null, maxCheckpoints: null };
    
    // Claude 3.5 Sonnet v2
    if (modelId.includes('claude-3-5-sonnet')) {
      return { minTokens: 1024, maxCheckpoints: 4 };
    }
    // Claude 3.5 Haiku
    if (modelId.includes('claude-3-5-haiku')) {
      return { minTokens: 2048, maxCheckpoints: 4 };
    }
    // Amazon Nova models
    if (modelId.includes('nova')) {
      return { minTokens: 1, maxCheckpoints: 1 };
    }
    return { minTokens: null, maxCheckpoints: null };
  };

  const modelDefaults = React.useMemo(() => getModelDefaults(modelId), [modelId]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="enable-caching"
          name="enable-caching"
          checked={enableCaching}
          onChange={(e) => setEnableCaching(e.target.checked)}
          disabled={isDisabled}
        />
        <label htmlFor="enable-caching" className="text-sm font-medium text-gray-700">
          {t(I18nKey.SETTINGS_FORM$ENABLE_PROMPT_CACHING_LABEL)}
        </label>
      </div>

      {enableCaching && (
        <div className="ml-6 flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$CACHE_TTL_SECONDS_LABEL)}
            </label>
            <input
              type="number"
              name="cache-ttl-seconds"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.cacheTtlSeconds ?? 300}
              min={60}
              max={3600}
              disabled={isDisabled}
            />
            <p className="text-xs text-gray-500">
              {t(I18nKey.SETTINGS_FORM$CACHE_TTL_SECONDS_HELP)}
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$CACHE_MIN_TOKENS_LABEL)}
            </label>
            <input
              type="number"
              name="cache-min-tokens"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.cacheMinTokens ?? modelDefaults.minTokens}
              placeholder={modelDefaults.minTokens?.toString() ?? t(I18nKey.SETTINGS_FORM$MODEL_SPECIFIC_PLACEHOLDER)}
              disabled={isDisabled}
            />
            <p className="text-xs text-gray-500">
              {t(I18nKey.SETTINGS_FORM$CACHE_MIN_TOKENS_HELP)}
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$CACHE_MAX_CHECKPOINTS_LABEL)}
            </label>
            <input
              type="number"
              name="cache-max-checkpoints"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.cacheMaxCheckpoints ?? modelDefaults.maxCheckpoints}
              placeholder={modelDefaults.maxCheckpoints?.toString() ?? t(I18nKey.SETTINGS_FORM$MODEL_SPECIFIC_PLACEHOLDER)}
              disabled={isDisabled}
            />
            <p className="text-xs text-gray-500">
              {t(I18nKey.SETTINGS_FORM$CACHE_MAX_CHECKPOINTS_HELP)}
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$CACHE_STRATEGY_LABEL)}
            </label>
            <select
              name="cache-strategy"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.cacheStrategy ?? 'default'}
              disabled={isDisabled}
            >
              <option value="default">{t(I18nKey.SETTINGS_FORM$CACHE_STRATEGY_DEFAULT)}</option>
              <option value="aggressive">{t(I18nKey.SETTINGS_FORM$CACHE_STRATEGY_AGGRESSIVE)}</option>
              <option value="conservative">{t(I18nKey.SETTINGS_FORM$CACHE_STRATEGY_CONSERVATIVE)}</option>
            </select>
            <p className="text-xs text-gray-500">
              {t(I18nKey.SETTINGS_FORM$CACHE_STRATEGY_HELP)}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}