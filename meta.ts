export interface VendorSkillMeta {
  official?: boolean;
  skills: Record<string, string>; // sourceSkillName -> outputSkillName
  source: string;
}

/**
 * Repositories to clone as submodules and generate skills from source
 */
export const submodules: Record<string, string> = {};

/**
 * Already generated skills, sync with their `skills/` directory
 */
export const vendors: Record<string, VendorSkillMeta> = {};

/**
 * Hand-written skills with personal preferences/tastes/recommendations
 */
export const manual: string[] = [];
