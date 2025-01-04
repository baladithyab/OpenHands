import React from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";

interface BedrockSettingsInputsProps {
  isDisabled?: boolean;
  defaultValues?: {
    guardrailId?: string;
    guardrailVersion?: string;
    guardrailTrace?: string;
    crossRegionTarget?: string;
  };
}

export function BedrockSettingsInputs({
  isDisabled,
  defaultValues = {},
}: BedrockSettingsInputsProps) {
  const { t } = useTranslation();
  const [enableGuardrails, setEnableGuardrails] = React.useState(!!defaultValues.guardrailId);
  const [enableCrossRegion, setEnableCrossRegion] = React.useState(!!defaultValues.crossRegionTarget);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="enable-guardrails"
          checked={enableGuardrails}
          onChange={(e) => setEnableGuardrails(e.target.checked)}
          disabled={isDisabled}
        />
        <label htmlFor="enable-guardrails" className="text-sm font-medium text-gray-700">
          {t(I18nKey.SETTINGS_FORM$BEDROCK_ENABLE_GUARDRAILS_LABEL)}
        </label>
      </div>

      {enableGuardrails && (
        <div className="ml-6 flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$BEDROCK_GUARDRAIL_ID_LABEL)}
            </label>
            <input
              type="text"
              name="bedrock-guardrail-id"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.guardrailId}
              disabled={isDisabled}
              placeholder="ff6ujrregl1q"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$BEDROCK_GUARDRAIL_VERSION_LABEL)}
            </label>
            <select
              name="bedrock-guardrail-version"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.guardrailVersion || "DRAFT"}
              disabled={isDisabled}
            >
              <option value="DRAFT">DRAFT</option>
              <option value="ACTIVE">ACTIVE</option>
            </select>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$BEDROCK_GUARDRAIL_TRACE_LABEL)}
            </label>
            <select
              name="bedrock-guardrail-trace"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.guardrailTrace || "disabled"}
              disabled={isDisabled}
            >
              <option value="disabled">Disabled</option>
              <option value="enabled">Enabled</option>
            </select>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="enable-cross-region"
          checked={enableCrossRegion}
          onChange={(e) => setEnableCrossRegion(e.target.checked)}
          disabled={isDisabled}
        />
        <label htmlFor="enable-cross-region" className="text-sm font-medium text-gray-700">
          {t(I18nKey.SETTINGS_FORM$BEDROCK_ENABLE_CROSS_REGION_LABEL)}
        </label>
      </div>

      {enableCrossRegion && (
        <div className="ml-6 flex flex-col gap-2">
          <label className="text-sm font-medium text-gray-700">
            {t(I18nKey.SETTINGS_FORM$BEDROCK_CROSS_REGION_TARGET_LABEL)}
          </label>
          <select
            name="bedrock-cross-region-target"
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            defaultValue={defaultValues.crossRegionTarget || "us"}
            disabled={isDisabled}
          >
            <option value="us">United States (us)</option>
            <option value="eu">Europe (eu)</option>
            <option value="ap">Asia Pacific (ap)</option>
          </select>
        </div>
      )}
    </div>
  );
}