import type { Finding, ScenarioId, TransferContext } from "./types";

// Explicitly labeled DEMO data. Canned reviews apply ONLY to the exact canned report text below.

export interface Scenario {
  id: ScenarioId;
  label: string;
  blurb: string;
  context: TransferContext;
  report: string;
  review: {
    status: "issues" | "clean" | "needs-info";
    summary: string;
    findings: Finding[];
    checks: string[];
  };
}

const baseRequest = `I need a plan for Study Alpha.

1. From our EFS volume at /mnt/efs/study-alpha/raw/, take only .fastq.gz files that are NOT inside any tmp/ folder. Send them to BOTH:
   - FSx for Lustre at /mnt/fsx/study-alpha/input/
   - S3 at s3://lab-demo-archive/study-alpha/raw/
2. Separately, from the partner SFTP at sftp://partner.example.org/exports/study-alpha/, take only .csv files and send them ONLY to the SMB share //research-share/validation/study-alpha/.

Keep each source's filters independent.`;

const baseEndpoints = [
  { label: "EFS source", kind: "Amazon EFS", value: "/mnt/efs/study-alpha/raw/" },
  { label: "FSx destination", kind: "FSx for Lustre", value: "/mnt/fsx/study-alpha/input/" },
  { label: "S3 destination", kind: "Amazon S3", value: "s3://lab-demo-archive/study-alpha/raw/" },
  { label: "SFTP source", kind: "SFTP", value: "sftp://partner.example.org/exports/study-alpha/" },
  { label: "SMB destination", kind: "SMB/CIFS", value: "//research-share/validation/study-alpha/" },
];

const baseInventories = [
  {
    label: "Example inventory — EFS (illustrative, not real)",
    files: [
      "raw/run01/S1_R1.fastq.gz",
      "raw/run01/S1_R2.fastq.gz",
      "raw/run01/tmp/partial.fastq.gz",
      "raw/run01/qc_report.html",
    ],
  },
  {
    label: "Example inventory — SFTP (illustrative, not real)",
    files: ["exports/study-alpha/samples.csv", "exports/study-alpha/readme.txt"],
  },
];

const correctReport = `## Proposed transfer plan — Study Alpha

> **Proposed operations only.** Nothing below has been run and no files have been transferred.

There are **two independent sources** and **three routes**. Filters are scoped per source and are not shared.

### Route 1 — EFS → FSx for Lustre
- **Source:** \`/mnt/efs/study-alpha/raw/\` (Amazon EFS)
- **Destination:** \`/mnt/fsx/study-alpha/input/\` (FSx for Lustre)
- **Filter:** name matches \`*.fastq.gz\` AND path does not contain \`/tmp/\`
- **Method:** \`rsync\` from a host that mounts both file systems

### Route 2 — EFS → Amazon S3
- **Source:** \`/mnt/efs/study-alpha/raw/\` (same source, same filter as Route 1)
- **Destination:** \`s3://lab-demo-archive/study-alpha/raw/\`
- **Filter:** name matches \`*.fastq.gz\` AND path does not contain \`/tmp/\`
- **Method:** \`aws s3 sync\` with include/exclude rules

### Route 3 — SFTP → SMB
- **Source:** \`sftp://partner.example.org/exports/study-alpha/\`
- **Destination:** \`//research-share/validation/study-alpha/\` (SMB/CIFS)
- **Filter:** name matches \`*.csv\` only
- **Method:** \`lftp mirror\` to a staging host that has the SMB share mounted

| Route | Source | Destination | Filter | Method |
|---|---|---|---|---|
| 1 | EFS raw/ | FSx input/ | *.fastq.gz AND not tmp/ | rsync |
| 2 | EFS raw/ | S3 raw/ | *.fastq.gz AND not tmp/ | aws s3 sync |
| 3 | SFTP exports/ | SMB validation/ | *.csv | lftp mirror |

Illustrative commands (for review, **not executed**):

\`\`\`bash
rsync -a --include='*/' --exclude='tmp/' --include='*.fastq.gz' --exclude='*' \\
  /mnt/efs/study-alpha/raw/ /mnt/fsx/study-alpha/input/

aws s3 sync /mnt/efs/study-alpha/raw/ s3://lab-demo-archive/study-alpha/raw/ \\
  --exclude '*' --include '*.fastq.gz' --exclude '*/tmp/*'

lftp -e "mirror --include-glob='*.csv' /exports/study-alpha/ /mnt/smb/validation/study-alpha/; quit" \\
  sftp://partner.example.org
\`\`\`

The SFTP \`.csv\` route never reaches FSx or S3, and the EFS \`.fastq.gz\` filter never applies to the SFTP source.`;

const wrongReport = `## Proposed transfer plan — Study Alpha

Here is the plan for moving the Study Alpha data.

### Route 1 — EFS → FSx for Lustre
- **Source:** \`/mnt/efs/study-alpha/raw/\`
- **Destination:** \`/mnt/fsx/study-alpha/inputs/\`
- **Filter:** \`*.fastq.gz\` OR path does not contain \`/tmp/\`
- **Method:** \`rsync\`

### Route 2 — SFTP → SMB
- **Source:** \`//research-share/validation/study-alpha/\`
- **Destination:** \`sftp://partner.example.org/exports/study-alpha/\`
- **Filter:** \`*.fastq.gz\` and \`*.csv\`
- **Method:** \`aws s3 sync\`

The EFS files were copied successfully to FSx in a test run.`;

const insufficientRequest = `Plan a transfer for Study Alpha: send the .fastq.gz files from our EFS raw folder to the Lustre scratch space, and archive them to the lab bucket. Partner CSVs should go to the validation share too.`;

const insufficientReport = `## Proposed transfer plan — Study Alpha (draft)

> **Proposed operations only.** Several endpoints were described but not specified; placeholders are marked.

### Route 1 — EFS → FSx for Lustre
- **Source:** \`/mnt/efs/study-alpha/raw/\` (assumed from "EFS raw folder")
- **Destination:** \`<FSx scratch path — not supplied>\`
- **Filter:** \`*.fastq.gz\`
- **Method:** \`rsync\` (pending mount details)

### Route 2 — EFS → Amazon S3
- **Destination:** \`s3://<lab bucket — not supplied>/\`
- **Filter:** \`*.fastq.gz\`
- **Method:** \`aws s3 sync\`

### Route 3 — Partner source → SMB
- **Source:** \`<partner location — not supplied>\`
- **Destination:** \`<validation share — not supplied>\`
- **Filter:** \`*.csv\`
- **Method:** to be decided once the partner protocol (SFTP, SMB, other) is known

Please confirm the missing paths before this plan can be finalised.`;

export const SCENARIOS: Record<ScenarioId, Scenario> = {
  correct: {
    id: "correct",
    label: "Demo · Correct plan",
    blurb: "Three routes, independent filters, proposed only.",
    context: { request: baseRequest, changes: [], endpoints: baseEndpoints, inventories: baseInventories },
    report: correctReport,
    review: {
      status: "clean",
      summary:
        "No issues found against the supplied request and endpoint list. All three requested routes are present with the correct direction, paths, per-source filters and suitable methods.",
      findings: [],
      checks: [
        "Every requested route is present (EFS→FSx, EFS→S3, SFTP→SMB)",
        "Source/destination roles match the request",
        "Paths match the supplied endpoints exactly",
        "Filters are scoped to the correct source; AND logic preserved",
        "Methods suit each storage pair",
        "No claims that transfers already happened",
      ],
    },
  },
  "wrong-route": {
    id: "wrong-route",
    label: "Demo · Incorrect route/filter",
    blurb: "Wrong path, reversed roles, mixed filters, missing route.",
    context: { request: baseRequest, changes: [], endpoints: baseEndpoints, inventories: baseInventories },
    report: wrongReport,
    review: {
      status: "issues",
      summary: "6 issues found. The plan contradicts the request in several places and omits a required route.",
      checks: [
        "Route coverage",
        "Source/destination direction",
        "Path accuracy",
        "Filter scope and boolean logic",
        "Method suitability",
        "Claims of completed actions",
      ],
      findings: [
        {
          id: "f1",
          severity: "high",
          kind: "contradiction",
          title: "FSx destination path differs",
          quote: "/mnt/fsx/study-alpha/inputs/",
          explanation: "The report adds an extra “s” to the FSx folder name, which would target a different directory.",
          requested: "/mnt/fsx/study-alpha/input/",
          proposed: "/mnt/fsx/study-alpha/inputs/",
          reference: "Request item 1 · Endpoint “FSx destination”",
        },
        {
          id: "f2",
          severity: "high",
          kind: "contradiction",
          title: "AND turned into OR",
          quote: "OR path does not contain",
          explanation:
            "With OR, any file outside tmp/ would be selected, even if it isn't a .fastq.gz file (e.g. qc_report.html in the example inventory).",
          requested: ".fastq.gz files AND not inside any tmp/ folder",
          proposed: "*.fastq.gz OR path does not contain /tmp/",
          reference: "Request item 1: “only .fastq.gz files that are NOT inside any tmp/ folder”",
        },
        {
          id: "f3",
          severity: "high",
          kind: "contradiction",
          title: "Source and destination are reversed",
          quote: "//research-share/validation/study-alpha/",
          explanation: "The SMB share is listed as the source and the partner SFTP as the destination — the opposite of what was asked.",
          requested: "SFTP → SMB",
          proposed: "SMB → SFTP",
          reference: "Request item 2",
        },
        {
          id: "f4",
          severity: "high",
          kind: "contradiction",
          title: "EFS filter applied to the SFTP route",
          quote: "and *.csv",
          explanation: "The .fastq.gz filter belongs only to the EFS source. The SFTP route should select .csv files only.",
          requested: "SFTP route: *.csv only",
          proposed: "*.fastq.gz and *.csv",
          reference: "Request: “Keep each source's filters independent.”",
        },
        {
          id: "f5",
          severity: "medium",
          kind: "contradiction",
          title: "Unsuitable method for SFTP → SMB",
          quote: "aws s3 sync",
          explanation: "aws s3 sync works with Amazon S3. Neither end of this route is S3.",
          requested: "A method that reads SFTP and writes to SMB",
          proposed: "aws s3 sync",
          reference: "Endpoints “SFTP source” and “SMB destination”",
        },
        {
          id: "f6",
          severity: "high",
          kind: "contradiction",
          title: "Claims a transfer already happened",
          quote: "The EFS files were copied successfully to FSx in a test run.",
          explanation:
            "This app only plans transfers. No run, log or evidence was supplied, so this claim is unsupported. The S3 archive route (EFS → s3://lab-demo-archive/study-alpha/raw/) is also missing entirely.",
          requested: "Proposed operations only; include the EFS → S3 route",
          proposed: "Reports a completed test copy; S3 route omitted",
          reference: "Request item 1 (“BOTH”) · No logs in supplied context",
        },
      ],
    },
  },
  insufficient: {
    id: "insufficient",
    label: "Demo · Insufficient information",
    blurb: "Destinations described but not specified.",
    context: {
      request: insufficientRequest,
      changes: [],
      endpoints: [{ label: "EFS source (described)", kind: "Amazon EFS", value: "“our EFS raw folder”" }],
      inventories: [],
    },
    report: insufficientReport,
    review: {
      status: "needs-info",
      summary:
        "Not enough information to confirm this plan. These are gaps in the supplied evidence, not contradictions — the report correctly marks them as placeholders.",
      checks: ["Route coverage", "Path accuracy against supplied endpoints", "No invented endpoints", "No completed-action claims"],
      findings: [
        {
          id: "n1",
          severity: "medium",
          kind: "missing-evidence",
          title: "EFS path is assumed",
          quote: "(assumed from \"EFS raw folder\")",
          explanation: "The request describes the folder but never gives a path, so /mnt/efs/study-alpha/raw/ can't be verified.",
          requested: "“our EFS raw folder”",
          proposed: "/mnt/efs/study-alpha/raw/ (assumed)",
          reference: "Request (no EFS path supplied)",
        },
        {
          id: "n2",
          severity: "medium",
          kind: "missing-evidence",
          title: "FSx and S3 destinations unknown",
          quote: "<FSx scratch path — not supplied>",
          explanation: "“Lustre scratch space” and “lab bucket” need concrete paths before routes 1–2 can be checked.",
          requested: "Lustre scratch space; lab bucket",
          proposed: "Placeholders",
          reference: "Request · Supplied endpoints list",
        },
        {
          id: "n3",
          severity: "medium",
          kind: "missing-evidence",
          title: "Partner source and protocol unknown",
          quote: "<partner location — not supplied>",
          explanation: "Without the partner's location and protocol, a transfer method can't be judged suitable.",
          requested: "“Partner CSVs should go to the validation share”",
          proposed: "Method to be decided",
          reference: "Request",
        },
      ],
    },
  },
};

export const SCENARIO_LIST = Object.values(SCENARIOS);
