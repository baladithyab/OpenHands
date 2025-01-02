import React from "react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";

interface AWSAuthInputsProps {
  isDisabled?: boolean;
  defaultValues?: {
    accessKeyId?: string;
    secretAccessKey?: string;
    sessionToken?: string;
    region?: string;
    profileName?: string;
    roleName?: string;
    sessionName?: string;
    webIdentityToken?: string;
    bedrockEndpoint?: string;
  };
  authType?: "keys" | "profile" | "role" | "oidc";
}

export function AWSAuthInputs({
  isDisabled,
  defaultValues = {},
  authType = "keys",
}: AWSAuthInputsProps) {
  const { t } = useTranslation();
  const [selectedAuthType, setSelectedAuthType] = React.useState(authType);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium text-gray-700">
          {t(I18nKey.SETTINGS_FORM$AWS_AUTH_TYPE_LABEL)}
        </label>
        <select
          name="aws-auth-type"
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={selectedAuthType}
          onChange={(e) => setSelectedAuthType(e.target.value as typeof authType)}
          disabled={isDisabled}
        >
          <option value="keys">{t(I18nKey.SETTINGS_FORM$AWS_AUTH_TYPE_KEYS)}</option>
          <option value="profile">{t(I18nKey.SETTINGS_FORM$AWS_AUTH_TYPE_PROFILE)}</option>
          <option value="role">{t(I18nKey.SETTINGS_FORM$AWS_AUTH_TYPE_ROLE)}</option>
          <option value="oidc">{t(I18nKey.SETTINGS_FORM$AWS_AUTH_TYPE_OIDC)}</option>
        </select>
      </div>

      {selectedAuthType === "keys" && (
        <>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$AWS_ACCESS_KEY_ID_LABEL)}
            </label>
            <input
              type="password"
              name="aws-access-key-id"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.accessKeyId}
              disabled={isDisabled}
              placeholder="AKIA..."
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$AWS_SECRET_ACCESS_KEY_LABEL)}
            </label>
            <input
              type="password"
              name="aws-secret-access-key"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.secretAccessKey}
              disabled={isDisabled}
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$AWS_SESSION_TOKEN_LABEL)}
            </label>
            <input
              type="password"
              name="aws-session-token"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.sessionToken}
              disabled={isDisabled}
              placeholder={t(I18nKey.SETTINGS_FORM$AWS_SESSION_TOKEN_PLACEHOLDER)}
            />
          </div>
        </>
      )}

      {selectedAuthType === "profile" && (
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-gray-700">
            {t(I18nKey.SETTINGS_FORM$AWS_PROFILE_NAME_LABEL)}
          </label>
          <input
            type="text"
            name="aws-profile-name"
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            defaultValue={defaultValues.profileName}
            disabled={isDisabled}
            placeholder="default"
          />
        </div>
      )}

      {selectedAuthType === "role" && (
        <>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$AWS_ROLE_NAME_LABEL)}
            </label>
            <input
              type="text"
              name="aws-role-name"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.roleName}
              disabled={isDisabled}
              placeholder="arn:aws:iam::123456789012:role/example-role"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t(I18nKey.SETTINGS_FORM$AWS_SESSION_NAME_LABEL)}
            </label>
            <input
              type="text"
              name="aws-session-name"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue={defaultValues.sessionName}
              disabled={isDisabled}
              placeholder="my-session"
            />
          </div>
        </>
      )}

      {selectedAuthType === "oidc" && (
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-gray-700">
            {t(I18nKey.SETTINGS_FORM$AWS_WEB_IDENTITY_TOKEN_LABEL)}
          </label>
          <input
            type="password"
            name="aws-web-identity-token"
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            defaultValue={defaultValues.webIdentityToken}
            disabled={isDisabled}
          />
        </div>
      )}

      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium text-gray-700">
          {t(I18nKey.SETTINGS_FORM$AWS_REGION_LABEL)}
        </label>
        <input
          type="text"
          name="aws-region"
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          defaultValue={defaultValues.region}
          disabled={isDisabled}
          placeholder="us-west-2"
        />
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium text-gray-700">
          {t(I18nKey.SETTINGS_FORM$AWS_BEDROCK_ENDPOINT_LABEL)}
        </label>
        <input
          type="text"
          name="aws-bedrock-endpoint"
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          defaultValue={defaultValues.bedrockEndpoint}
          disabled={isDisabled}
          placeholder="https://bedrock-runtime.us-west-2.amazonaws.com"
        />
      </div>
    </div>
  );
}