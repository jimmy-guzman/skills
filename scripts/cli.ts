import { execSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import * as p from "@clack/prompts";

// eslint-disable-next-line import-x/extensions -- Node ESM requires .ts extension for TypeScript imports
import { manual, submodules, vendors } from "../meta.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

function exec(cmd: string, cwd = root): string {
  return execSync(cmd, {
    cwd,
    encoding: "utf8",
    stdio: ["pipe", "pipe", "pipe"],
  }).trim();
}

function execSafe(cmd: string, cwd = root): null | string {
  try {
    return exec(cmd, cwd);
  } catch {
    return null;
  }
}

function getGitSha(dir: string): null | string {
  return execSafe("git rev-parse HEAD", dir);
}

function submoduleExists(path: string): boolean {
  const gitmodules = join(root, ".gitmodules");

  if (!existsSync(gitmodules)) return false;

  const content = readFileSync(gitmodules, "utf8");

  return content.includes(`path = ${path}`);
}

const RE_SUBMODULE_PATH = /path\s*=\s*(.+)/g;

function getExistingSubmodulePaths(): string[] {
  const gitmodules = join(root, ".gitmodules");

  if (!existsSync(gitmodules)) return [];

  const content = readFileSync(gitmodules, "utf8");
  const matches = content.matchAll(RE_SUBMODULE_PATH);

  return Array.from(matches, (match) => match[1].trim());
}

function removeSubmodule(submodulePath: string): void {
  execSafe(`git submodule deinit -f ${submodulePath}`);
  const gitModulesPath = join(root, ".git", "modules", submodulePath);

  if (existsSync(gitModulesPath)) {
    rmSync(gitModulesPath, { recursive: true });
  }

  exec(`git rm -f ${submodulePath}`);
}

interface Project {
  name: string;
  path: string;
  type: "source" | "vendor";
  url: string;
}

interface VendorConfig {
  skills: Record<string, string>;
  source: string;
}

async function initSubmodules(skipPrompt = false) {
  const allProjects: Project[] = [
    ...Object.entries(submodules).map(([name, url]) => {
      return { name, path: `sources/${name}`, type: "source" as const, url };
    }),
    ...Object.entries(vendors).map(([name, config]) => {
      return {
        name,
        path: `vendor/${name}`,
        type: "vendor" as const,
        url: (config as VendorConfig).source,
      };
    }),
  ];

  const spinner = p.spinner();

  // Check for extra submodules that are not in meta.ts
  const existingSubmodulePaths = getExistingSubmodulePaths();
  const expectedPaths = new Set(allProjects.map((p) => p.path));
  const extraSubmodules = existingSubmodulePaths.filter((path) => {
    return !expectedPaths.has(path);
  });

  if (extraSubmodules.length > 0) {
    p.log.warn(`Found ${extraSubmodules.length} submodule(s) not in meta.ts:`);
    for (const path of extraSubmodules) {
      p.log.message(`  - ${path}`);
    }

    const shouldRemove = skipPrompt
      ? true
      : await p.confirm({
          initialValue: true,
          message: "Remove these extra submodules?",
        });

    if (p.isCancel(shouldRemove)) {
      p.cancel("Cancelled");

      return;
    }

    if (shouldRemove) {
      for (const submodulePath of extraSubmodules) {
        spinner.start(`Removing submodule: ${submodulePath}`);
        try {
          removeSubmodule(submodulePath);
          spinner.stop(`Removed: ${submodulePath}`);
        } catch (error) {
          spinner.stop(`Failed to remove ${submodulePath}: ${String(error)}`);
        }
      }
    }
  }

  const existingProjects = allProjects.filter((p) => submoduleExists(p.path));
  const newProjects = allProjects.filter((p) => !submoduleExists(p.path));

  if (newProjects.length === 0) {
    p.log.info("All submodules already initialized");

    return;
  }

  const selected = skipPrompt
    ? newProjects
    : await p.multiselect({
        initialValues: newProjects,
        message: "Select projects to initialize",
        options: newProjects.map((project) => {
          return { hint: project.url, label: `${project.name} (${project.type})`, value: project };
        }),
      });

  if (p.isCancel(selected)) {
    p.cancel("Cancelled");

    return;
  }

  for (const project of selected) {
    spinner.start(`Adding submodule: ${project.name}`);

    const parentDir = join(root, dirname(project.path));

    if (!existsSync(parentDir)) {
      mkdirSync(parentDir, { recursive: true });
    }

    try {
      exec(`git submodule add ${project.url} ${project.path}`);
      spinner.stop(`Added: ${project.name}`);
    } catch (error) {
      spinner.stop(`Failed to add ${project.name}: ${String(error)}`);
    }
  }

  p.log.success("Submodules initialized");

  if (existingProjects.length > 0) {
    p.log.info(`Already initialized: ${existingProjects.map((p) => p.name).join(", ")}`);
  }
}

function syncSubmodules() {
  const spinner = p.spinner();

  spinner.start("Updating submodules...");
  try {
    exec("git submodule update --remote --merge");
    spinner.stop("Submodules updated");
  } catch (error) {
    spinner.stop(`Failed to update submodules: ${String(error)}`);

    return;
  }

  // Sync Type 2 skills
  for (const [vendorName, config] of Object.entries(vendors)) {
    const vendorConfig = config as VendorConfig;
    const vendorPath = join(root, "vendor", vendorName);
    const vendorSkillsPath = join(vendorPath, "skills");

    if (!existsSync(vendorPath)) {
      p.log.warn(`Vendor submodule not found: ${vendorName}. Run init first.`);
      continue;
    }

    if (!existsSync(vendorSkillsPath)) {
      p.log.warn(`No skills directory in vendor/${vendorName}/skills/`);
      continue;
    }

    for (const [sourceSkillName, outputSkillName] of Object.entries(vendorConfig.skills)) {
      const sourceSkillPath = join(vendorSkillsPath, sourceSkillName);
      const outputPath = join(root, "skills", outputSkillName);

      if (!existsSync(sourceSkillPath)) {
        p.log.warn(`Skill not found: vendor/${vendorName}/skills/${sourceSkillName}`);
        continue;
      }

      spinner.start(`Syncing skill: ${sourceSkillName} -> ${outputSkillName}`);

      if (existsSync(outputPath)) {
        rmSync(outputPath, { recursive: true });
      }

      mkdirSync(outputPath, { recursive: true });

      const files = readdirSync(sourceSkillPath, {
        recursive: true,
        withFileTypes: true,
      });

      for (const file of files) {
        if (file.isFile()) {
          const fullPath = join(file.parentPath, file.name);
          const relativePath = fullPath.replace(sourceSkillPath, "");
          const destPath = join(outputPath, relativePath);

          const destDir = dirname(destPath);

          if (!existsSync(destDir)) {
            mkdirSync(destDir, { recursive: true });
          }

          cpSync(fullPath, destPath);
        }
      }

      // Copy LICENSE file from vendor repo root if it exists
      const licenseNames = [
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        "license",
        "license.md",
        "license.txt",
      ];

      for (const licenseName of licenseNames) {
        const licensePath = join(vendorPath, licenseName);

        if (existsSync(licensePath)) {
          cpSync(licensePath, join(outputPath, "LICENSE.md"));

          break;
        }
      }

      // Update SYNC.md
      const sha = getGitSha(vendorPath);
      const syncPath = join(outputPath, "SYNC.md");
      const date = new Date().toISOString().split("T")[0];

      const syncContent = `# Sync Info

- **Source:** \`vendor/${vendorName}/skills/${sourceSkillName}\`
- **Git SHA:** \`${sha}\`
- **Synced:** ${date}
`;

      writeFileSync(syncPath, syncContent);

      spinner.stop(`Synced: ${sourceSkillName} -> ${outputSkillName}`);
    }
  }

  p.log.success("All skills synced");
}

function checkUpdates() {
  const spinner = p.spinner();

  spinner.start("Fetching remote changes...");

  try {
    exec("git submodule foreach git fetch");
    spinner.stop("Fetched remote changes");
  } catch (error) {
    spinner.stop(`Failed to fetch: ${String(error)}`);

    return;
  }

  const updates: { behind: number; name: string; type: string }[] = [];

  for (const name of Object.keys(submodules)) {
    const path = join(root, "sources", name);

    if (!existsSync(path)) continue;

    const behind = execSafe("git rev-list HEAD..@{u} --count", path);
    const count = behind ? Number.parseInt(behind, 10) : 0;

    if (count > 0) {
      updates.push({ behind: count, name, type: "source" });
    }
  }

  for (const [name, config] of Object.entries(vendors)) {
    const vendorConfig = config as VendorConfig;
    const path = join(root, "vendor", name);

    if (!existsSync(path)) continue;

    const behind = execSafe("git rev-list HEAD..@{u} --count", path);
    const count = behind ? Number.parseInt(behind, 10) : 0;

    if (count > 0) {
      const skillNames = Object.values(vendorConfig.skills).join(", ");

      updates.push({
        behind: count,
        name: `${name} (${skillNames})`,
        type: "vendor",
      });
    }
  }

  if (updates.length === 0) {
    p.log.success("All submodules are up to date");
  } else {
    p.log.info("Updates available:");
    for (const update of updates) {
      p.log.message(`  ${update.name} (${update.type}): ${update.behind} commits behind`);
    }
  }
}

function getExpectedSkillNames(): Set<string> {
  const expected = new Set<string>();

  for (const name of Object.keys(submodules)) {
    expected.add(name);
  }

  for (const config of Object.values(vendors)) {
    const vendorConfig = config as VendorConfig;

    for (const outputName of Object.values(vendorConfig.skills)) {
      expected.add(outputName);
    }
  }

  for (const name of manual) {
    expected.add(name);
  }

  return expected;
}

function getExistingSkillNames(): string[] {
  const skillsDir = join(root, "skills");

  if (!existsSync(skillsDir)) return [];

  return readdirSync(skillsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name);
}

async function cleanup(skipPrompt = false) {
  const spinner = p.spinner();

  let hasChanges = false;

  const allProjects: Project[] = [
    ...Object.entries(submodules).map(([name, url]) => {
      return { name, path: `sources/${name}`, type: "source" as const, url };
    }),
    ...Object.entries(vendors).map(([name, config]) => {
      return {
        name,
        path: `vendor/${name}`,
        type: "vendor" as const,
        url: (config as VendorConfig).source,
      };
    }),
  ];

  const existingSubmodulePaths = getExistingSubmodulePaths();
  const expectedSubmodulePaths = new Set(allProjects.map((p) => p.path));
  const extraSubmodules = existingSubmodulePaths.filter(
    (path) => !expectedSubmodulePaths.has(path),
  );

  if (extraSubmodules.length > 0) {
    p.log.warn(`Found ${extraSubmodules.length} submodule(s) not in meta.ts:`);
    for (const path of extraSubmodules) {
      p.log.message(`  - ${path}`);
    }

    const shouldRemove = skipPrompt
      ? true
      : await p.confirm({
          initialValue: true,
          message: "Remove these extra submodules?",
        });

    if (p.isCancel(shouldRemove)) {
      p.cancel("Cancelled");

      return;
    }

    if (shouldRemove) {
      hasChanges = true;
      for (const submodulePath of extraSubmodules) {
        spinner.start(`Removing submodule: ${submodulePath}`);
        try {
          removeSubmodule(submodulePath);
          spinner.stop(`Removed: ${submodulePath}`);
        } catch (error) {
          spinner.stop(`Failed to remove ${submodulePath}: ${String(error)}`);
        }
      }
    }
  }

  // Find and remove extra skills
  const existingSkills = getExistingSkillNames();
  const expectedSkills = getExpectedSkillNames();
  const extraSkills = existingSkills.filter((name) => !expectedSkills.has(name));

  if (extraSkills.length > 0) {
    p.log.warn(`Found ${extraSkills.length} skill(s) not in meta.ts:`);
    for (const name of extraSkills) {
      p.log.message(`  - skills/${name}`);
    }

    const shouldRemove = skipPrompt
      ? true
      : await p.confirm({
          initialValue: true,
          message: "Remove these extra skills?",
        });

    if (p.isCancel(shouldRemove)) {
      p.cancel("Cancelled");

      return;
    }

    if (shouldRemove) {
      hasChanges = true;
      for (const skillName of extraSkills) {
        spinner.start(`Removing skill: ${skillName}`);
        try {
          rmSync(join(root, "skills", skillName), { recursive: true });
          spinner.stop(`Removed: skills/${skillName}`);
        } catch (error) {
          spinner.stop(`Failed to remove skills/${skillName}: ${String(error)}`);
        }
      }
    }
  }

  if (!hasChanges && extraSubmodules.length === 0 && extraSkills.length === 0) {
    p.log.success("Everything is clean, no unused submodules or skills found");
  } else if (hasChanges) {
    p.log.success("Cleanup completed");
  }
}

async function main() {
  const args = process.argv.slice(2);
  const skipPrompt = args.includes("-y") || args.includes("--yes");
  const command = args.find((arg) => !arg.startsWith("-"));

  if (command === "init") {
    p.intro("Skills Manager - Init");
    await initSubmodules(skipPrompt);
    p.outro("Done");

    return;
  }

  if (command === "sync") {
    p.intro("Skills Manager - Sync");
    syncSubmodules();
    p.outro("Done");

    return;
  }

  if (command === "check") {
    p.intro("Skills Manager - Check");
    checkUpdates();
    p.outro("Done");

    return;
  }

  if (command === "cleanup") {
    p.intro("Skills Manager - Cleanup");
    await cleanup(skipPrompt);
    p.outro("Done");

    return;
  }

  if (skipPrompt) {
    p.log.error("Command required when using -y flag");
    p.log.info("Available commands: init, sync, check, cleanup");
    process.exit(1);
  }

  p.intro("Skills Manager");

  const action = await p.select({
    message: "What would you like to do?",
    options: [
      {
        hint: "Pull latest and sync Type 2 skills",
        label: "Sync submodules",
        value: "sync",
      },
      {
        hint: "Add new submodules",
        label: "Init submodules",
        value: "init",
      },
      {
        hint: "See available updates",
        label: "Check updates",
        value: "check",
      },
      {
        hint: "Remove unused submodules and skills",
        label: "Cleanup",
        value: "cleanup",
      },
    ],
  });

  if (p.isCancel(action)) {
    p.cancel("Cancelled");
    process.exit(0);
  }

  switch (action) {
    case "check": {
      checkUpdates();

      break;
    }
    case "cleanup": {
      await cleanup();

      break;
    }
    case "init": {
      await initSubmodules();

      break;
    }
    case "sync": {
      syncSubmodules();

      break;
    }
    default: {
      break;
    }
  }

  p.outro("Done");
}

// eslint-disable-next-line n/no-top-level-await -- private CLI script, not published
await main();
