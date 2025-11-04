// Action Executor Module for EasyForm
// This module handles the execution of various form actions

const ActionExecutor = {
  // Default delay between actions (milliseconds)
  defaultDelay: 100,

  /**
   * Execute a list of actions
   * @param {Array} actions - List of action objects
   * @param {boolean} autoExecute - Whether to execute immediately
   * @returns {Promise<Object>} Execution result
   */
  async executeActions(actions, autoExecute = true) {
    console.log('[ActionExecutor] 🚀 executeActions called:', {
      actionsCount: actions?.length,
      autoExecute,
      timestamp: new Date().toISOString(),
      stackTrace: new Error().stack
    });

    if (!autoExecute) {
      console.log('[ActionExecutor] ⏸️ AutoExecute is false, skipping execution');
      return { success: true, message: 'Actions stored for manual execution' };
    }

    const results = [];
    let successCount = 0;
    let failCount = 0;
    let skipCount = 0;

    console.log('[ActionExecutor] 🔄 Starting action execution loop...');
    for (const action of actions) {
      try {
        const executionResult = await this.executeAction(action);

        if (executionResult?.skipped) {
          skipCount++;
          results.push({
            action,
            success: true,
            skipped: true,
            message: executionResult.reason
          });
        } else {
          successCount++;
          results.push({
            action,
            success: true
          });
        }

        // Small delay between actions to simulate human behavior
        await this.delay(this.defaultDelay);
      } catch (error) {
        failCount++;
        results.push({
          action,
          success: false,
          error: error.message
        });
        console.error('Action failed:', action, error);
      }
    }

    const finalResult = {
      success: failCount === 0,
      successCount,
      failCount,
      skipCount,
      results
    };

    console.log('[ActionExecutor] 🏁 executeActions finished:', finalResult);
    return finalResult;
  },

  /**
   * Execute a single action
   * @param {Object} action - Action object
   */
  async executeAction(action) {
  const actionType = action.type ?? action.action_type ?? action.actionType;
  const selector = action.selector ?? action.cssSelector ?? action.target ?? action.field_selector;
  const value = action.value ?? action.answer ?? action.text;

    if (!actionType) {
      throw new Error('Action type is missing');
    }

    if (!selector) {
      throw new Error('Action selector is missing');
    }

    const requiresValue = new Set(['fillText', 'setText', 'selectCheckbox', 'selectDropdown']);

    if (requiresValue.has(actionType) && value == null) {
      console.warn('Skipping action with missing value:', action);
      return {
        skipped: true,
        reason: 'Value missing'
      };
    }

    const element = document.querySelector(selector);
    if (!element) {
      throw new Error(`Element not found: ${selector}`);
    }

    switch (actionType) {
      case 'fillText':
        return this.fillText(element, value);

      case 'click':
        return this.click(element);

      case 'selectRadio':
        return this.selectRadio(element);

      case 'selectCheckbox':
        return this.selectCheckbox(element, value);

      case 'selectDropdown':
        return this.selectDropdown(element, value);

      case 'setText':
        return this.setText(element, value);

      default:
        throw new Error(`Unknown action type: ${actionType}`);
    }
  },

  /**
   * Fill text input field
   */
  fillText(element, value) {
    // Focus element
    element.focus();

    // Set value
  element.value = value ?? '';

    // Trigger input events to simulate user typing
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));

    // Blur element
    element.blur();
  },

  /**
   * Set text (alternative method)
   */
  setText(element, value) {
    return this.fillText(element, value);
  },

  /**
   * Click an element
   */
  click(element) {
    // Scroll element into view
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Trigger click events
    element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    element.click();
  },

  /**
   * Select a radio button
   */
  selectRadio(element) {
    if (element.type !== 'radio') {
      throw new Error('Element is not a radio button');
    }

    if (element.checked) {
      return { skipped: true, reason: 'Radio already selected' };
    }

    element.focus();
    element.click();

    if (!element.checked) {
      element.checked = true;
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
    }
  },

  /**
   * Select/deselect a checkbox
   */
  selectCheckbox(element, value) {
    if (element.type !== 'checkbox') {
      throw new Error('Element is not a checkbox');
    }

    // Value can be boolean or string ('true'/'false')
    const shouldCheck = value === true || value === 'true' || value === '1';

    if (element.checked === shouldCheck) {
      return { skipped: true, reason: 'Checkbox already in desired state' };
    }

    element.focus();
    element.click();

    if (element.checked !== shouldCheck) {
      element.checked = shouldCheck;
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
    }
  },

  /**
   * Select dropdown option
   */
  selectDropdown(element, value) {
    if (element.tagName !== 'SELECT') {
      throw new Error('Element is not a select dropdown');
    }

    // Try to find option by value or text
    let optionFound = false;

    // Try by value
    for (const option of element.options) {
      if (option.value === value || option.text === value) {
        option.selected = true;
        optionFound = true;
        break;
      }
    }

    if (!optionFound) {
      throw new Error(`Option not found: ${value}`);
    }

    element.dispatchEvent(new Event('change', { bubbles: true }));
  },

  /**
   * Delay helper
   */
  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  },

  /**
   * Highlight an element (for debugging/visualization)
   */
  highlightElement(element, duration = 2000) {
    const originalOutline = element.style.outline;
    element.style.outline = '2px solid #4CAF50';

    setTimeout(() => {
      element.style.outline = originalOutline;
    }, duration);
  }
};

// Make available globally
window.ActionExecutor = ActionExecutor;
