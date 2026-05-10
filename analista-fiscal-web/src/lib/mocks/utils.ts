export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function mockLatency(min = 50, max = 120): Promise<void> {
  const ms = Math.floor(min + Math.random() * (max - min));
  await sleep(ms);
}

export function mockMaybeError(probability = 0.02): void {
  if (Math.random() < probability) {
    throw new Error("mock_random_failure");
  }
}

export function pseudoUuid(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}
