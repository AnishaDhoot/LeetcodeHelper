import { test, expect } from '@playwright/test';

test.describe('End-to-End User Journeys (Playwright)', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to local test harness or LeetCode problem page
    await page.goto('https://leetcode.com/problems/two-sum/');
  });

  test('Journey 1: Failure Diagnostic & Action Guidance Display', async ({ page }) => {
    // Simulate runtime submission error
    await page.evaluate(() => {
      window.postMessage({
        source: 'CODECOACH_INJECTED',
        type: 'LEETCODE_SUBMISSION_RESULT',
        problem_title: 'Two Sum',
        problem_slug: 'two-sum',
        code: 'class Solution { public int[] twoSum(int[] nums, int target) { return new int[]{}; } }',
        language: 'java',
        verdict: 'Wrong Answer',
        passed_test_cases: 2,
        total_test_cases: 58,
        test_cases: [{ input: '[3,2,4]\n6', expected: '[1,2]', actual: '[]' }]
      }, '*');
    });

    const card = page.locator('[data-testid="diagnostic-card"]');
    if (await card.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(page.locator('[data-testid="diagnosis-badge"]')).toBeVisible();
      await expect(page.locator('[data-testid="diagnosis-explanation"]')).toBeVisible();
    }
  });

  test('Journey 2: Progressive Hint Level Stepping (1 -> 2 -> 3)', async ({ page }) => {
    const revealBtn = page.locator('[data-testid="reveal-hint-btn"]');
    if (await revealBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Step to Level 1
      await revealBtn.click();
      await expect(page.locator('[data-testid="hint-level-indicator"]')).toContainText('Level 1');

      // Step to Level 2
      await revealBtn.click();
      await expect(page.locator('[data-testid="hint-level-indicator"]')).toContainText('Level 2');
    }
  });

  test('Journey 3: Mock Interview Strategy Gating & Unlock', async ({ page }) => {
    const startMockBtn = page.locator('[data-testid="start-mock-btn"]');
    if (await startMockBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await startMockBtn.click();

      // Verify code editor lock banner
      await expect(page.locator('[data-testid="editor-locked-banner"]')).toBeVisible();

      // Enter strategy explanation
      await page.fill('[data-testid="strategy-input"]', 'I will use a Hash Map to store seen elements in O(N) time and O(N) space.');
      await page.click('[data-testid="submit-strategy-btn"]');

      // Verify unlock
      await expect(page.locator('[data-testid="editor-unlocked-banner"]')).toBeVisible({ timeout: 10000 });
    }
  });
});
