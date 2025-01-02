interface ValidationError {
  field: string;
  message: string;
}

interface BedrockSettings {
  // Caching settings
  enable_caching?: boolean;
  cache_ttl_seconds?: number;
  cache_min_tokens?: number | null;
  cache_max_checkpoints?: number | null;
  cache_strategy?: string;

  // Routing settings
  enable_routing?: boolean;
  routing_strategy?: string;
  routing_model_family?: string | null;
  routing_cross_region?: boolean;
  routing_metrics_enabled?: boolean;

  // Model info
  LLM_MODEL?: string;
}

const SUPPORTED_CACHING_MODELS = [
  'claude-3-5-sonnet-20241022',
  'claude-3-5-sonnet-20240620',
  'claude-3-5-haiku-20241022',
  'claude-3-haiku-20240307',
  'claude-3-opus-20240229',
  'nova-micro-v1',
  'nova-lite-v1',
  'nova-pro-v1'
];

const SUPPORTED_ROUTING_FAMILIES = ['anthropic', 'meta'];

export function validateBedrockSettings(settings: BedrockSettings): ValidationError[] {
  const errors: ValidationError[] = [];

  // Extract model info
  const modelId = settings.LLM_MODEL?.split('/').pop() || '';
  const isBedrockModel = settings.LLM_MODEL?.startsWith('bedrock/');
  const isSupportedCachingModel = SUPPORTED_CACHING_MODELS.some(model => modelId.includes(model));

  // Validate caching settings
  if (settings.enable_caching) {
    // Only validate if caching is enabled
    if (!isBedrockModel) {
      errors.push({
        field: 'enable_caching',
        message: 'Prompt caching is only supported for AWS Bedrock models'
      });
    } else if (!isSupportedCachingModel) {
      errors.push({
        field: 'enable_caching',
        message: 'This model does not support prompt caching'
      });
    } else {
      // Validate TTL
      if (settings.cache_ttl_seconds !== undefined) {
        if (settings.cache_ttl_seconds < 60 || settings.cache_ttl_seconds > 3600) {
          errors.push({
            field: 'cache_ttl_seconds',
            message: 'Cache TTL must be between 60 and 3600 seconds'
          });
        }
      }

      // Validate min tokens if specified
      if (settings.cache_min_tokens !== null && settings.cache_min_tokens !== undefined) {
        const minTokens = getModelMinTokens(modelId);
        if (settings.cache_min_tokens < minTokens) {
          errors.push({
            field: 'cache_min_tokens',
            message: `Minimum tokens must be at least ${minTokens} for this model`
          });
        }
      }

      // Validate max checkpoints if specified
      if (settings.cache_max_checkpoints !== null && settings.cache_max_checkpoints !== undefined) {
        const maxCheckpoints = getModelMaxCheckpoints(modelId);
        if (settings.cache_max_checkpoints > maxCheckpoints) {
          errors.push({
            field: 'cache_max_checkpoints',
            message: `Maximum checkpoints cannot exceed ${maxCheckpoints} for this model`
          });
        }
      }

      // Validate strategy
      if (settings.cache_strategy && !['default', 'aggressive', 'conservative'].includes(settings.cache_strategy)) {
        errors.push({
          field: 'cache_strategy',
          message: 'Invalid caching strategy'
        });
      }
    }
  }

  // Validate routing settings
  if (settings.enable_routing) {
    // Only validate if routing is enabled
    if (!isBedrockModel) {
      errors.push({
        field: 'enable_routing',
        message: 'Prompt routing is only supported for AWS Bedrock models'
      });
    } else {
      // Validate strategy
      if (settings.routing_strategy && !['balanced', 'performance_focused', 'cost_focused'].includes(settings.routing_strategy)) {
        errors.push({
          field: 'routing_strategy',
          message: 'Invalid routing strategy'
        });
      }

      // Validate model family if specified
      if (settings.routing_model_family && !SUPPORTED_ROUTING_FAMILIES.includes(settings.routing_model_family)) {
        errors.push({
          field: 'routing_model_family',
          message: 'Unsupported model family for routing'
        });
      }

      // Validate cross-region routing
      if (settings.routing_cross_region && !settings.routing_metrics_enabled) {
        errors.push({
          field: 'routing_cross_region',
          message: 'CloudWatch metrics must be enabled for cross-region routing'
        });
      }
    }
  }

  return errors;
}

function getModelMinTokens(modelId: string): number {
  if (modelId.includes('claude-3-5-sonnet')) {
    return 1024;
  }
  if (modelId.includes('claude-3-5-haiku')) {
    return 2048;
  }
  if (modelId.includes('nova')) {
    return 1;
  }
  return 1024; // Default for other models
}

function getModelMaxCheckpoints(modelId: string): number {
  if (modelId.includes('claude')) {
    return 4;
  }
  if (modelId.includes('nova')) {
    return 1;
  }
  return 4; // Default for other models
}

export function isBedrockCachingSupported(modelId?: string): boolean {
  if (!modelId) return false;
  return SUPPORTED_CACHING_MODELS.some(model => modelId.includes(model));
}

export function isBedrockRoutingSupported(modelId?: string): boolean {
  if (!modelId) return false;
  const family = modelId.split('/')[1]?.split('.')[0];
  return SUPPORTED_ROUTING_FAMILIES.includes(family);
}