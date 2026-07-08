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

// The two demo identities (recipient learner + issuing organization) are
// configured via .env — labels and profile ids live in .env.example, not here,
// so a different org can customize its own demo run without editing code.
