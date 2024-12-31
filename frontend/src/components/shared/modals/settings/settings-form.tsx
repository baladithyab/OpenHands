import { useLocation } from "react-router";
import { useTranslation } from "react-i18next";
import React from "react";
import posthog from "posthog-js";
import { organizeModelsAndProviders } from "#/utils/organize-models-and-providers";
import { getDefaultSettings, Settings } from "#/services/settings";
import { extractModelAndProvider } from "#/utils/extract-model-and-provider";
import { DangerModal } from "../confirmation-modals/danger-modal";
import { I18nKey } from "#/i18n/declaration";
import { extractSettings, saveSettingsView } from "#/utils/settings-utils";
import { useEndSession } from "#/hooks/use-end-session";
import { ModalButton } from "../../buttons/modal-button";
import { AdvancedOptionSwitch } from "../../inputs/advanced-option-switch";
import { AgentInput } from "../../inputs/agent-input";
import { APIKeyInput } from "../../inputs/api-key-input";
import { BaseUrlInput } from "../../inputs/base-url-input";
import { ConfirmationModeSwitch } from "../../inputs/confirmation-mode-switch";
import { CustomModelInput } from "../../inputs/custom-model-input";
import { SecurityAnalyzerInput } from "../../inputs/security-analyzers-input";
import { PromptCachingInputs } from "../../inputs/prompt-caching-inputs";
import { PromptRoutingInputs } from "../../inputs/prompt-routing-inputs";
import { ModalBackdrop } from "../modal-backdrop";
import { ModelSelector } from "./model-selector";
import { useSaveSettings } from "#/hooks/mutation/use-save-settings";

interface SettingsFormProps {
  disabled?: boolean;
  settings: Settings;
  models: string[];
  agents: string[];
  securityAnalyzers: string[];
  onClose: () => void;
}

export function SettingsForm({
  disabled,
  settings,
  models,
  agents,
  securityAnalyzers,
  onClose,
}: SettingsFormProps) {
  const { mutateAsync: saveSettings } = useSaveSettings();
  const endSession = useEndSession();

  const location = useLocation();
  const { t } = useTranslation();

  const formRef = React.useRef<HTMLFormElement>(null);

  const advancedAlreadyInUse = React.useMemo(() => {
    if (models.length > 0) {
      const organizedModels = organizeModelsAndProviders(models);
      const { provider, model } = extractModelAndProvider(
        settings.LLM_MODEL || "",
      );
      const isKnownModel =
        provider in organizedModels &&
        organizedModels[provider].models.includes(model);

      const isUsingSecurityAnalyzer = !!settings.SECURITY_ANALYZER;
      const isUsingConfirmationMode = !!settings.CONFIRMATION_MODE;
      const isUsingBaseUrl = !!settings.LLM_BASE_URL;
      const isUsingCustomModel = !!settings.LLM_MODEL && !isKnownModel;
      const isUsingAdvancedCaching = settings.enable_caching && (
        settings.cache_min_tokens !== null ||
        settings.cache_max_checkpoints !== null ||
        settings.cache_strategy !== 'default'
      );
      const isUsingRouting = settings.enable_routing;

      return (
        isUsingSecurityAnalyzer ||
        isUsingConfirmationMode ||
        isUsingBaseUrl ||
        isUsingCustomModel ||
        isUsingAdvancedCaching ||
        isUsingRouting
      );
    }

    return false;
  }, [settings, models]);

  const [showAdvancedOptions, setShowAdvancedOptions] =
    React.useState(advancedAlreadyInUse);
  const [confirmResetDefaultsModalOpen, setConfirmResetDefaultsModalOpen] =
    React.useState(false);
  const [confirmEndSessionModalOpen, setConfirmEndSessionModalOpen] =
    React.useState(false);

  const resetOngoingSession = () => {
    if (location.pathname.startsWith("/conversations/")) {
      endSession();
    }
  };

  const handleFormSubmission = async (formData: FormData) => {
    const keys = Array.from(formData.keys());
    const isUsingAdvancedOptions = keys.includes("use-advanced-options");
    const newSettings = extractSettings(formData);

    saveSettingsView(isUsingAdvancedOptions ? "advanced" : "basic");
    await saveSettings(newSettings, { onSuccess: onClose });
    resetOngoingSession();

    posthog.capture("settings_saved", {
      LLM_MODEL: newSettings.LLM_MODEL,
      LLM_API_KEY: newSettings.LLM_API_KEY ? "SET" : "UNSET",
      ENABLE_CACHING: newSettings.enable_caching,
      ENABLE_ROUTING: newSettings.enable_routing,
    });
  };

  const handleConfirmResetSettings = async () => {
    await saveSettings(getDefaultSettings(), { onSuccess: onClose });
    resetOngoingSession();
    posthog.capture("settings_reset");
  };

  const handleConfirmEndSession = () => {
    const formData = new FormData(formRef.current ?? undefined);
    handleFormSubmission(formData);
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);

    if (location.pathname.startsWith("/conversations/")) {
      setConfirmEndSessionModalOpen(true);
    } else {
      handleFormSubmission(formData);
    }
  };

  return (
    <div>
      <form
        ref={formRef}
        data-testid="settings-form"
        className="flex flex-col gap-6"
        onSubmit={handleSubmit}
      >
        <div className="flex flex-col gap-2">
          <AdvancedOptionSwitch
            isDisabled={!!disabled}
            showAdvancedOptions={showAdvancedOptions}
            setShowAdvancedOptions={setShowAdvancedOptions}
          />

          {showAdvancedOptions && (
            <>
              <CustomModelInput
                isDisabled={!!disabled}
                defaultValue={settings.LLM_MODEL}
              />

              <BaseUrlInput
                isDisabled={!!disabled}
                defaultValue={settings.LLM_BASE_URL}
              />
            </>
          )}

          {!showAdvancedOptions && (
            <ModelSelector
              isDisabled={disabled}
              models={organizeModelsAndProviders(models)}
              currentModel={settings.LLM_MODEL}
            />
          )}

          <APIKeyInput
            isDisabled={!!disabled}
            isSet={settings.LLM_API_KEY === "SET"}
          />

          {showAdvancedOptions && (
            <>
              <AgentInput
                isDisabled={!!disabled}
                defaultValue={settings.AGENT}
                agents={agents}
              />

              <SecurityAnalyzerInput
                isDisabled={!!disabled}
                defaultValue={settings.SECURITY_ANALYZER}
                securityAnalyzers={securityAnalyzers}
              />

              <ConfirmationModeSwitch
                isDisabled={!!disabled}
                defaultSelected={settings.CONFIRMATION_MODE}
              />

              <div className="mt-4 border-t pt-4">
                <h3 className="mb-4 text-lg font-medium">
                  {t(I18nKey.SETTINGS_FORM$PROMPT_CACHING_SECTION_TITLE)}
                </h3>
                <PromptCachingInputs
                  isDisabled={!!disabled}
                  defaultValues={{
                    enableCaching: settings.enable_caching,
                    cacheTtlSeconds: settings.cache_ttl_seconds,
                    cacheMinTokens: settings.cache_min_tokens,
                    cacheMaxCheckpoints: settings.cache_max_checkpoints,
                    cacheStrategy: settings.cache_strategy,
                  }}
                  modelId={settings.LLM_MODEL}
                />
              </div>

              <div className="mt-4 border-t pt-4">
                <h3 className="mb-4 text-lg font-medium">
                  {t(I18nKey.SETTINGS_FORM$PROMPT_ROUTING_SECTION_TITLE)}
                </h3>
                <PromptRoutingInputs
                  isDisabled={!!disabled}
                  defaultValues={{
                    enableRouting: settings.enable_routing,
                    routingStrategy: settings.routing_strategy,
                    routingModelFamily: settings.routing_model_family,
                    routingCrossRegion: settings.routing_cross_region,
                    routingMetricsEnabled: settings.routing_metrics_enabled,
                  }}
                />
              </div>
            </>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <ModalButton
              disabled={disabled}
              type="submit"
              text={t(I18nKey.SETTINGS_FORM$SAVE_LABEL)}
              className="bg-[#4465DB] w-full"
            />
            <ModalButton
              text={t(I18nKey.SETTINGS_FORM$CLOSE_LABEL)}
              className="bg-[#737373] w-full"
              onClick={onClose}
            />
          </div>
          <ModalButton
            disabled={disabled}
            text={t(I18nKey.SETTINGS_FORM$RESET_TO_DEFAULTS_LABEL)}
            variant="text-like"
            className="text-danger self-start"
            onClick={() => {
              setConfirmResetDefaultsModalOpen(true);
            }}
          />
        </div>
      </form>

      {confirmResetDefaultsModalOpen && (
        <ModalBackdrop>
          <DangerModal
            testId="reset-defaults-modal"
            title={t(I18nKey.SETTINGS_FORM$ARE_YOU_SURE_LABEL)}
            description={t(
              I18nKey.SETTINGS_FORM$ALL_INFORMATION_WILL_BE_DELETED_MESSAGE,
            )}
            buttons={{
              danger: {
                text: t(I18nKey.SETTINGS_FORM$RESET_TO_DEFAULTS_LABEL),
                onClick: handleConfirmResetSettings,
              },
              cancel: {
                text: t(I18nKey.SETTINGS_FORM$CANCEL_LABEL),
                onClick: () => setConfirmResetDefaultsModalOpen(false),
              },
            }}
          />
        </ModalBackdrop>
      )}
      {confirmEndSessionModalOpen && (
        <ModalBackdrop>
          <DangerModal
            title={t(I18nKey.SETTINGS_FORM$END_SESSION_LABEL)}
            description={t(
              I18nKey.SETTINGS_FORM$CHANGING_WORKSPACE_WARNING_MESSAGE,
            )}
            buttons={{
              danger: {
                text: t(I18nKey.SETTINGS_FORM$END_SESSION_LABEL),
                onClick: handleConfirmEndSession,
              },
              cancel: {
                text: t(I18nKey.SETTINGS_FORM$CANCEL_LABEL),
                onClick: () => setConfirmEndSessionModalOpen(false),
              },
            }}
          />
        </ModalBackdrop>
      )}
    </div>
  );
}