import { request } from "../api";
import type {
  Inspection,
  StageRun,
  Timeline,
  Recording,
  Artifact,
  PiReceipt,
} from "./contracts";
import { assertRecording } from "./model";

export function read<T>(path: string, token: string, signal: AbortSignal) {
  return request<T>(path, token, undefined, "GET", signal);
}
export async function recording(
  id: string,
  token: string,
  signal: AbortSignal,
): Promise<Recording> {
  const path = "/workflow-runs/" + encodeURIComponent(id);
  const [inspection, stages, timeline] = await Promise.all([
    read<Inspection>(path + "/inspection", token, signal),
    read<{ run_id: string; stages: StageRun[] }>(
      path + "/stages",
      token,
      signal,
    ),
    read<Timeline>(path + "/timeline?limit=500", token, signal),
  ]);
  if (stages.run_id !== id || inspection.run.id !== id)
    throw new Error("Run identity mismatch");
  const attachedStages = stages.stages.map((stage) => {
    const attached = inspection.pi_links?.[stage.id];
    if (stage.pi_run_id && attached && stage.pi_run_id !== attached)
      throw new Error("Receipt identity mismatch");
    return { ...stage, pi_run_id: attached || stage.pi_run_id };
  });
  return assertRecording({ ...inspection, stages: attachedStages, timeline });
}
export function artifact(
  id: string,
  stage: string,
  token: string,
  signal: AbortSignal,
) {
  return read<Artifact>(
    `/workflow-runs/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(stage)}`,
    token,
    signal,
  );
}
export function receipt(
  id: string,
  attempt: string,
  token: string,
  signal: AbortSignal,
) {
  return read<{
    run_id: string;
    attempt_id: string;
    stage_id: string;
    receipt: PiReceipt;
  }>(
    `/workflow-runs/${encodeURIComponent(id)}/stages/${encodeURIComponent(attempt)}/pi-receipt`,
    token,
    signal,
  );
}
