import React from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";

interface PromptRoutingInputsProps {
  isDisabled?: boolean;
  defaultValues?: {
    enableRouting?: boolean;
    routingStrategy?: string;
    routingModelFamily?: string;
    routingCrossRegion?: boolean;
    routingMetricsEnabled?: boolean;
  };
}

export function PromptRoutingInputs({
  isDisabled,
  defaultValues = {},
}: PromptRoutingInputsProps) {
  const { t } = useTranslation();
  const [enableRouting, setEnableRouting] = React.useState(defaultValues.enableRouting ?? false);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="enable-routing"
          name="enable-routing"
          checked={enableRouting}
          onChange={(e) => setEnableRouting(e.target.checked)}
          disabled={isDisabled}
        />
        <label htmlFor="enable-routing" className="text-sm font-medium text-gray-700">
          {t(I18nKey.SETTINGS_FORM$ENABLE_PROMPT_ROUTING_LABEL)}
        </label>
        <span className="ml-2 rounded-full bg-blue-100 px-2 py-1 text-xs font-medium text-blue-800">
          Beta
        </span>
      </div>

      {enableRouting && (
        <div className="ml-6 flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$ROUTING_STRATEGY_LABEL)}
            </label>
            <select
              name="routing-strategy"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.routingStrategy ?? 'balanced'}
              disabled={isDisabled}
            >
              <option value="balanced">{t(I18nKey.SETTINGS_FORM$ROUTING_STRATEGY_BALANCED)}</option>
              <option value="performance_focused">{t(I18nKey.SETTINGS_FORM$ROUTING_STRATEGY_PERFORMANCE)}</option>
              <option value="cost_focused">{t(I18nKey.SETTINGS_FORM$ROUTING_STRATEGY_COST)}</option>
            </select>
            <p className="text-xs text-gray-500">
              {t(I18nKey.SETTINGS_FORM$ROUTING_STRATEGY_HELP)}
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$ROUTING_MODEL_FAMILY_LABEL)}
            </label>
            <select
              name="routing-model-family"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.routingModelFamily ?? ''}
              disabled={isDisabled}
            >
              <option value="">{t(I18nKey.SETTINGS_FORM$ROUTING_MODEL_FAMILY_AUTO)}</option>
              <option value="anthropic">{t(I18nKey.SETTINGS_FORM$ROUTING_MODEL_FAMILY_ANTHROPIC)}</option>
              <option value="meta">{t(I18nKey.SETTINGS_FORM$ROUTING_MODEL_FAMILY_META)}</option>
            </select>
            <p className="text-xs text-gray-500">
              {t(I18nKey.SETTINGS_FORM$ROUTING_MODEL_FAMILY_HELP)}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="routing-cross-region"
              name="routing-cross-region"
              checked={defaultValues.routingCrossRegion ?? false}
              disabled={isDisabled}
            />
            <label htmlFor="routing-cross-region" className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$ROUTING_CROSS_REGION_LABEL)}
            </label>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="routing-metrics-enabled"
              name="routing-metrics-enabled"
              checked={defaultValues.routingMetricsEnabled ?? true}
              disabled={isDisabled}
            />
            <label htmlFor="routing-metrics-enabled" className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$ROUTING_METRICS_ENABLED_LABEL)}
            </label>
          </div>
        </div>
      )}
    </div>
  );
}