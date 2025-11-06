import { createContext, useCallback, useEffect, useMemo, useState } from 'react';

const ThemeContext = createContext({
  theme: 'light',
  mode: 'system',
  setMode: () => {},
  cycleMode: () => {},
  isAuto: true,
});

// Export for useTheme hook
export { ThemeContext };


const STORAGE_KEY = 'easyform-theme';
const MODE_SEQUENCE = ['system', 'light', 'dark'];
const getSystemTheme = () => {
  if (typeof window === 'undefined') {
    return 'light';
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

const getInitialState = () => {
  if (typeof window === 'undefined') {
    return { theme: 'light', mode: 'system' };
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  
  if (stored === 'light' || stored === 'dark') {
    return { theme: stored, mode: stored };
  }

  return { theme: getSystemTheme(), mode: 'system' };
};

const persistMode = (mode) => {
  if (typeof window === 'undefined') {
    return;
  }
  if (mode === 'system') {
    window.localStorage.removeItem(STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, mode);
};

export function ThemeProvider({ children }) {
  const [state, setState] = useState(() => getInitialState());

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    const root = document.documentElement;
    const isDark = state.theme === 'dark';
    
    if (isDark) {
      root.classList.add('dark');
      document.body.classList.add('dark');
    } else {
      root.classList.remove('dark');
      document.body.classList.remove('dark');
    }
    
    root.style.colorScheme = state.theme;
    root.dataset.theme = state.theme;
  }, [state.theme]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleChange = (event) => {
      setState((current) => {
        if (current.mode !== 'system') {
          return current;
        }
        return { mode: 'system', theme: event.matches ? 'dark' : 'light' };
      });
    };

    mediaQuery.addEventListener('change', handleChange);

    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const setMode = useCallback((nextMode) => {
    setState(() => {
      const normalized = MODE_SEQUENCE.includes(nextMode) ? nextMode : 'system';
      const resolvedTheme = normalized === 'system' ? getSystemTheme() : normalized;
      persistMode(normalized);
      return { mode: normalized, theme: resolvedTheme };
    });
  }, []);

  const cycleMode = useCallback(() => {
    setState((current) => {
      const currentIndex = MODE_SEQUENCE.indexOf(current.mode);
      const nextMode = MODE_SEQUENCE[(currentIndex + 1) % MODE_SEQUENCE.length];
      const resolvedTheme = nextMode === 'system' ? getSystemTheme() : nextMode;
      
      persistMode(nextMode);
      return { mode: nextMode, theme: resolvedTheme };
    });
  }, []);

  const value = useMemo(
    () => ({
      theme: state.theme,
      mode: state.mode,
      setMode,
      cycleMode,
      isAuto: state.mode === 'system',
    }),
    [state.theme, state.mode, setMode, cycleMode]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

ThemeProvider.displayName = 'ThemeProvider';
