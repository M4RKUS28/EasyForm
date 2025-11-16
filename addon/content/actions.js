// Action Executor Module for EasyForm
// This module handles the execution of various form actions

const ActionExecutor = {
  // Default delay between actions (milliseconds)
  defaultDelay: 100,

  /**
   * Lightweight logger helper to keep messages consistent
   */
  log(message, details) {
    if (details !== undefined) {
      console.log(`[ActionExecutor] ${message}`, details);
    } else {
      console.log(`[ActionExecutor] ${message}`);
    }
  },

  /**
   * Execute a list of actions
   * @param {Array} actions - List of action objects
   * @param {boolean} autoExecute - Whether to execute immediately
   * @returns {Promise<Object>} Execution result
   */
  async executeActions(actions, autoExecute = true) {
    this.log('🚀 executeActions called:', {
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

    this.log('🔄 Starting action execution loop...');
    for (const action of actions) {
      try {
        this.log('▶️ Executing action', action);
        const executionResult = await this.executeAction(action);

        if (executionResult?.skipped) {
          skipCount++;
          results.push({
            action,
            success: true,
            skipped: true,
            message: executionResult.reason
          });
          this.log('⏭️ Action skipped', {
            selector: action.selector,
            type: action.action_type ?? action.type,
            reason: executionResult.reason
          });
        } else {
          successCount++;
          results.push({
            action,
            success: true
          });
          this.log('✅ Action completed', {
            selector: action.selector,
            type: action.action_type ?? action.type
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
        console.error('[ActionExecutor] ❌ Action failed:', action, error);
      }
    }

    const finalResult = {
      success: failCount === 0,
      successCount,
      failCount,
      skipCount,
      results
    };

    this.log('🏁 executeActions finished:', finalResult);
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

    this.log('🔍 Resolving selector', { actionType, selector });
    const element = document.querySelector(selector);
    if (!element) {
      throw new Error(`Element not found: ${selector}`);
    }

    this.log('🎯 Element resolved', {
      actionType,
      selector,
      tagName: element.tagName,
      role: element.getAttribute?.('role') ?? null,
      inputType: element.type ?? null
    });

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
  async fillText(element, value) {
    const target = this.resolveTextTarget(element);
    if (!target) {
      throw new Error('Element is not a text input');
    }

    this.log('✏️ fillText target resolved', {
      mode: target.mode,
      tagName: target.element.tagName,
      role: target.element.getAttribute?.('role') ?? null
    });

    const textValue = value != null ? String(value) : '';

    if (target.mode === 'aceEditor') {
      await this.fillAceEditor(target.element, textValue);
      return;
    }

    if (target.mode === 'contentEditable') {
      this.fillContentEditable(target.element, textValue);
      return;
    }

    const inputElement = target.element;
    inputElement.focus();
    inputElement.value = textValue;
    inputElement.dispatchEvent(new Event('input', { bubbles: true }));
    inputElement.dispatchEvent(new Event('change', { bubbles: true }));
    inputElement.blur();
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
  async selectRadio(element) {
    const control = this.resolveControl(element, 'radio');

    if (!control) {
      throw new Error('Element is not a radio button');
    }

    this.log('🎚️ selectRadio control resolved', {
      mode: control.mode,
      tagName: control.element.tagName,
      role: control.element.getAttribute?.('role') ?? null,
      ariaChecked: this.getAriaChecked(control.element)
    });

    if (control.mode === 'input') {
      const inputElement = control.element;
      if (inputElement.checked) {
        return { skipped: true, reason: 'Radio already selected' };
      }

      inputElement.focus();
      inputElement.click();

      if (!inputElement.checked) {
        inputElement.checked = true;
        inputElement.dispatchEvent(new Event('input', { bubbles: true }));
        inputElement.dispatchEvent(new Event('change', { bubbles: true }));
      }
      return;
    }

    const ariaElement = control.element;
    const currentState = this.getAriaChecked(ariaElement);
    if (currentState === true) {
      return { skipped: true, reason: 'Radio already selected' };
    }

    await this.performAriaToggle(ariaElement, true, 'radio');
  },

  /**
   * Select/deselect a checkbox
   */
  async selectCheckbox(element, value) {
    const control = this.resolveControl(element, 'checkbox');

    if (!control) {
      throw new Error('Element is not a checkbox');
    }

    this.log('☑️ selectCheckbox control resolved', {
      mode: control.mode,
      tagName: control.element.tagName,
      role: control.element.getAttribute?.('role') ?? null,
      ariaChecked: this.getAriaChecked(control.element)
    });

    const shouldCheck = this.toBoolean(value);
    this.log('☑️ Desired checkbox state', { shouldCheck, rawValue: value });

    if (control.mode === 'input') {
      const inputElement = control.element;
      if (inputElement.checked === shouldCheck) {
        return { skipped: true, reason: 'Checkbox already in desired state' };
      }

      inputElement.focus();
      inputElement.click();

      if (inputElement.checked !== shouldCheck) {
        inputElement.checked = shouldCheck;
        inputElement.dispatchEvent(new Event('input', { bubbles: true }));
        inputElement.dispatchEvent(new Event('change', { bubbles: true }));
      }
      return;
    }

    const ariaElement = control.element;
    const currentState = this.getAriaChecked(ariaElement);
    if (currentState !== null && currentState === shouldCheck) {
      return { skipped: true, reason: 'Checkbox already in desired state' };
    }

    await this.performAriaToggle(ariaElement, shouldCheck, 'checkbox');
  },

  /**
   * Select dropdown option
   */
  async selectDropdown(element, value) {
    if (element.tagName === 'SELECT') {
      // Try to find option by value or text
      let optionFound = false;

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
      return;
    }

    const role = element.getAttribute?.('role');
    if (role === 'listbox') {
      await this.selectFromAriaListbox(element, value);
      return;
    }

    if (role === 'option') {
      this.click(element);
      return;
    }

    throw new Error('Element is not a select dropdown');
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
  },

  resolveControl(element, role) {
    if (!element || typeof role !== 'string') {
      return null;
    }

    const normalizedRole = role.toLowerCase();

    if (element !== document && element !== window) {
      this.log('🧭 resolveControl inspecting element', {
        requestedRole: normalizedRole,
        tagName: element.tagName,
        role: element.getAttribute?.('role') ?? null
      });
    }

    if (this.isInputOfType(element, normalizedRole)) {
      return { element, mode: 'input' };
    }

    if (this.hasAriaRole(element, normalizedRole)) {
      return { element, mode: 'aria' };
    }

    const inputSelector = normalizedRole === 'radio'
      ? "input[type='radio']"
      : normalizedRole === 'checkbox'
        ? "input[type='checkbox']"
        : '';

    if (inputSelector) {
      const descendantInput = element.querySelector(inputSelector);
      if (descendantInput && descendantInput !== element && this.isInputOfType(descendantInput, normalizedRole)) {
        return { element: descendantInput, mode: 'input' };
      }
    }

    const ariaDescendant = element.querySelector(`[role='${normalizedRole}']`);
    if (ariaDescendant && ariaDescendant !== element) {
      this.log('🧭 resolveControl using descendant aria role', {
        requestedRole: normalizedRole,
        tagName: ariaDescendant.tagName,
        role: ariaDescendant.getAttribute?.('role') ?? null
      });
      return { element: ariaDescendant, mode: 'aria' };
    }

    return null;
  },

  resolveTextTarget(element) {
    if (!element) {
      return null;
    }

    // Check for ACE Editor first
    const aceEditor = this.findAceEditor(element);
    if (aceEditor) {
      return { element: aceEditor, mode: 'aceEditor' };
    }

    if (this.isStandardTextInput(element)) {
      return { element, mode: 'input' };
    }

    if (this.isContentEditable(element)) {
      return { element, mode: 'contentEditable' };
    }

    if (element instanceof HTMLInputElement && (element.type || '').toLowerCase() === 'hidden') {
      const visibleInput = this.findVisibleInputForHidden(element);
      if (visibleInput) {
        return this.resolveTextTarget(visibleInput);
      }
    }

    const descendant = element.querySelector('input, textarea, [contenteditable="true"], [role="textbox"]');
    if (descendant && descendant !== element) {
      this.log('🧭 resolveTextTarget exploring descendant', {
        selectorMatch: descendant.tagName,
        role: descendant.getAttribute?.('role') ?? null
      });
      return this.resolveTextTarget(descendant);
    }

    return null;
  },

  isStandardTextInput(element) {
    if (element instanceof HTMLTextAreaElement) {
      return true;
    }

    if (element instanceof HTMLInputElement) {
      const type = (element.type || 'text').toLowerCase();
      return !['button', 'submit', 'reset', 'checkbox', 'radio', 'file', 'image', 'range', 'color', 'hidden'].includes(type);
    }

    return false;
  },

  isContentEditable(element) {
    if (!element || typeof element.getAttribute !== 'function') {
      return false;
    }

    if (element.isContentEditable) {
      return true;
    }

    const attr = element.getAttribute('contenteditable');
    if (attr && attr.toLowerCase() === 'true') {
      return true;
    }

    const role = element.getAttribute('role');
    return role && role.toLowerCase() === 'textbox';
  },

  fillContentEditable(element, value) {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    element.focus();

    const selection = window.getSelection?.();
    if (selection) {
      selection.removeAllRanges();
      const range = document.createRange();
      range.selectNodeContents(element);
      selection.addRange(range);
      selection.deleteFromDocument();
    }

    element.textContent = value;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    element.blur();
  },

  /**
   * Find ACE Editor instance for an element
   * @param {HTMLElement} element - The element to check
   * @returns {HTMLElement|null} The ACE editor container or null
   */
  findAceEditor(element) {
    if (!element) {
      return null;
    }

    // Check if element itself is an ACE editor container
    if (element.classList && element.classList.contains('ace_editor')) {
      return element;
    }

    // Check if element is inside an ACE editor
    const aceContainer = element.closest('.ace_editor');
    if (aceContainer) {
      return aceContainer;
    }

    // Check if element has an ACE editor as descendant
    const aceDescendant = element.querySelector('.ace_editor');
    if (aceDescendant) {
      return aceDescendant;
    }

    return null;
  },

  /**
   * Fill ACE Editor with value
   * @param {HTMLElement} aceContainer - The ACE editor container element
   * @param {string} value - The value to set
   */
  async fillAceEditor(aceContainer, value) {
    this.log('📝 fillAceEditor detected', {
      containerClass: aceContainer.className,
      id: aceContainer.id
    });

    // Try multiple methods to get the editor instance
    let editor = null;
    let method = 'unknown';

    // Method 1: Direct env.editor property (most reliable)
    if (aceContainer.env?.editor) {
      editor = aceContainer.env.editor;
      method = 'env.editor';
    }

    // Method 2: Check if editor instance is directly attached
    if (!editor && aceContainer.editor) {
      editor = aceContainer.editor;
      method = 'container.editor';
    }

    // Method 3: Try using ID with ace.edit (if container has ID)
    if (!editor && aceContainer.id && window.ace) {
      try {
        const tempEditor = window.ace.edit(aceContainer.id);
        if (tempEditor && typeof tempEditor.setValue === 'function') {
          editor = tempEditor;
          method = 'ace.edit(id)';
        }
      } catch (e) {
        this.log('⚠️ ace.edit(id) failed', e.message);
      }
    }

    // Method 4: Search through all ace editors
    if (!editor && window.ace?.edit) {
      try {
        // Some versions store editor in aceContainer directly
        for (const key in aceContainer) {
          if (aceContainer[key]?.setValue && aceContainer[key]?.session) {
            editor = aceContainer[key];
            method = `container.${key}`;
            break;
          }
        }
      } catch (e) {
        this.log('⚠️ Property search failed', e.message);
      }
    }

    // If we found an editor instance, use the API
    if (editor && typeof editor.setValue === 'function') {
      this.log('✅ ACE Editor API found via', method);

      try {
        // Scroll into view
        aceContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Use ACE's setValue method
        // The second parameter (-1) moves cursor to the start
        editor.setValue(value, -1);

        // Trigger focus to ensure the editor is active
        editor.focus();

        // Clear selection
        editor.clearSelection();

        // Trigger change event to ensure listeners are notified
        if (editor.session) {
          editor.session.getDocument().setValue(value);
        }

        this.log('✅ ACE Editor content set successfully');
        return;
      } catch (e) {
        this.log('❌ ACE Editor API failed', e.message);
        // Fall through to fallback method
      }
    }

    // Fallback: Try aggressive text manipulation
    this.log('⚠️ Using fallback methods - ACE Editor API not available');

    // Method 5: Aggressive textarea manipulation with Ctrl+A
    const textarea = aceContainer.querySelector('textarea.ace_text-input');
    if (textarea) {
      try {
        this.log('🔧 Attempting aggressive textarea method');

        // Scroll into view first
        aceContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
        await this.delay(100);

        // Focus the textarea
        textarea.focus();
        await this.delay(50);

        // First, try to select all with Ctrl+A
        textarea.dispatchEvent(new KeyboardEvent('keydown', {
          key: 'a',
          code: 'KeyA',
          ctrlKey: true,
          bubbles: true,
          cancelable: true
        }));

        await this.delay(50);

        // Delete selected content
        textarea.dispatchEvent(new KeyboardEvent('keydown', {
          key: 'Delete',
          code: 'Delete',
          bubbles: true,
          cancelable: true
        }));

        await this.delay(50);

        // Now set the value directly
        textarea.value = value;

        // Dispatch input event with the full value
        const inputEvent = new InputEvent('input', {
          bubbles: true,
          cancelable: true,
          inputType: 'insertText',
          data: value
        });
        textarea.dispatchEvent(inputEvent);

        // Dispatch change event
        textarea.dispatchEvent(new Event('change', { bubbles: true }));

        await this.delay(50);

        // Trigger a key event to force ACE to update
        textarea.dispatchEvent(new KeyboardEvent('keyup', {
          key: 'Enter',
          code: 'Enter',
          bubbles: true
        }));

        this.log('✅ Aggressive textarea method completed');
        return;
      } catch (e) {
        this.log('❌ Aggressive textarea method failed', e.message);
      }
    }

    // Method 6: Try clicking and using execCommand
    try {
      this.log('🔧 Attempting click + execCommand method');

      // Click somewhere in the editor to ensure focus
      const content = aceContainer.querySelector('.ace_content');
      if (content) {
        content.click();
        await this.delay(50);
      }

      // Try execCommand if supported
      if (document.queryCommandSupported && document.queryCommandSupported('selectAll')) {
        document.execCommand('selectAll', false, null);
        await this.delay(50);
        document.execCommand('delete', false, null);
        await this.delay(50);
        document.execCommand('insertText', false, value);

        this.log('✅ execCommand method completed');
        return;
      }
    } catch (e) {
      this.log('❌ execCommand method failed', e.message);
    }

    this.log('⚠️ All fallback methods completed - verify content was updated');
  },

  isInputOfType(element, type) {
    return element instanceof HTMLInputElement && (element.type || '').toLowerCase() === type;
  },

  hasAriaRole(element, role) {
    if (!element || typeof element.getAttribute !== 'function') {
      return false;
    }
    const ariaRole = element.getAttribute('role');
    return ariaRole && ariaRole.toLowerCase() === role;
  },

  getAriaChecked(element) {
    if (!element) {
      return null;
    }

    if (typeof element.checked === 'boolean') {
      return element.checked;
    }

    const ariaChecked = element.getAttribute?.('aria-checked');
    if (ariaChecked === 'true') {
      return true;
    }
    if (ariaChecked === 'false') {
      return false;
    }
    if (ariaChecked === 'mixed') {
      return true;
    }

    const ariaPressed = element.getAttribute?.('aria-pressed');
    if (ariaPressed === 'true') {
      return true;
    }
    if (ariaPressed === 'false') {
      return false;
    }

    const datasetChecked = element.dataset?.checked ?? element.getAttribute?.('data-checked');
    if (datasetChecked === 'true') {
      return true;
    }
    if (datasetChecked === 'false') {
      return false;
    }

    return null;
  },

  async performAriaToggle(element, shouldCheck, role) {
    this.log('🔁 performAriaToggle start', {
      role,
      desiredState: shouldCheck,
      currentState: this.getAriaChecked(element)
    });
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    element.focus();

    this.click(element);
    const postClick = await this.waitForAriaState(element, shouldCheck);
    this.log('🔁 performAriaToggle after click', {
      role,
      desiredState: shouldCheck,
      currentState: postClick
    });
    if (postClick === shouldCheck) {
      return;
    }

    this.triggerKeyboardToggle(element, role === 'radio' ? ' ' : ' ');
    const postKey = await this.waitForAriaState(element, shouldCheck);
    this.log('🔁 performAriaToggle after keypress', {
      role,
      desiredState: shouldCheck,
      currentState: postKey
    });
    if (postKey === shouldCheck) {
      return;
    }

    if (typeof element.setAttribute === 'function') {
      element.setAttribute('aria-checked', shouldCheck ? 'true' : 'false');
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
      const forcedState = this.getAriaChecked(element);
      this.log('🔁 performAriaToggle forced state', {
        role,
        desiredState: shouldCheck,
        currentState: forcedState
      });
      if (forcedState === shouldCheck) {
        return;
      }
    }

    throw new Error(`Failed to update ${role} state`);
  },

  triggerKeyboardToggle(element, key = ' ') {
    if (!element || typeof element.dispatchEvent !== 'function') {
      return;
    }

    const eventInit = {
      key,
      code: key === ' ' ? 'Space' : 'Enter',
      bubbles: true,
      cancelable: true,
    };

    element.dispatchEvent(new KeyboardEvent('keydown', eventInit));
    element.dispatchEvent(new KeyboardEvent('keyup', eventInit));
  },

  toBoolean(value) {
    if (value === true || value === 'true' || value === '1' || value === 1) {
      return true;
    }
    if (value === false || value === 'false' || value === '0' || value === 0) {
      return false;
    }
    return false;
  },

  findVisibleInputForHidden(hiddenInput) {
    if (!hiddenInput) {
      return null;
    }

    const name = hiddenInput.getAttribute?.('name');
    if (name && name.endsWith('_sentinel')) {
      const normalizedName = name.replace(/_sentinel$/i, '');
      const candidate = document.querySelector(`input[name='${normalizedName}']`);
      if (candidate && this.isStandardTextInput(candidate)) {
        return candidate;
      }
    }

    const container = hiddenInput.closest('[jsname], [role], .rFrNMe, .quantumWizTextinputPapertextareaEl, .quantumWizTextinputPaperinputEl');
    if (container) {
      const candidate = container.querySelector('input[type="text"], textarea, [contenteditable="true"], [role="textbox"]');
      if (candidate) {
        return candidate;
      }
    }

    const fallback = document.querySelector('input[type="text"][aria-label], textarea[aria-label]');
    return fallback || null;
  },

  async waitForAriaState(element, desiredState, retries = 6, delayMs = 50) {
    for (let attempt = 0; attempt <= retries; attempt++) {
      const current = this.getAriaChecked(element);
      if (current === desiredState) {
        return current;
      }
      if (attempt === retries) {
        return current;
      }
      await this.delay(delayMs);
    }
    return this.getAriaChecked(element);
  },

  async selectFromAriaListbox(listboxElement, value) {
    this.click(listboxElement);
    await this.delay(100);

    const options = Array.from(document.querySelectorAll("[role='option']"));
    let target = null;
    for (const option of options) {
      const optionValue = option.getAttribute('data-value') ?? option.getAttribute('data-answer-value');
      const optionLabel = option.textContent?.trim();
      if (optionValue === value || optionLabel === value) {
        target = option;
        break;
      }
    }

    if (!target) {
      throw new Error(`Option not found in listbox: ${value}`);
    }

    this.click(target);
    await this.delay(100);
  },
};

// Make available globally
window.ActionExecutor = ActionExecutor;
