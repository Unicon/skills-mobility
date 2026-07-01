import { createHash } from 'node:crypto';

/**
 * Deterministically derive a LearnCard seed (64-char hex) from a committed,
 * non-secret demo label. This keeps the demo identities *fixed* across
 * presenters without committing a raw high-entropy key: the label is public,
 * the seed is derived at runtime, and the minted bearer tokens (which are the
 * real secrets) stay gitignored and regenerable. See ADR-0020.
 */
export function deriveSeed(label) {
  return createHash('sha256').update(`skills-mobility-demo:${label}`).digest('hex');
}

// The two fixed demo identities. Labels are intentionally public.
export const ISSUER_LABEL = 'issuer';
export const RECIPIENT_LABEL = 'learner';
export const RECIPIENT_PROFILE_ID = 'smi-demo-learner';
export const ISSUER_PROFILE_ID = 'smi-demo-issuer';
