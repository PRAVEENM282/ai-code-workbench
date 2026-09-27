import Editor, { type OnMount } from '@monaco-editor/react';
import { useEffect, useRef } from 'react';
import type { editor } from 'monaco-editor';
import type { Finding, Language } from '../api/types';
import copy from '../locales/en.json';
import { toMonacoMarkers } from '../editor/diagnostics';

interface CodeEditorProps {
  language: Language;
  value: string;
  findings: Finding[];
  onChange: (value: string) => void;
  onAnalyze: () => void;
  onGenerate: () => void;
}

export function CodeEditor({ language, value, findings, onChange, onAnalyze, onGenerate }: CodeEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null);
  const analyzeRef = useRef(onAnalyze);
  const generateRef = useRef(onGenerate);
  analyzeRef.current = onAnalyze;
  generateRef.current = onGenerate;

  const handleMount: OnMount = (instance, monaco) => {
    editorRef.current = instance;
    monacoRef.current = monaco;
    const style = getComputedStyle(document.documentElement);
    monaco.editor.defineTheme('workbench-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: { 'editor.background': style.getPropertyValue('--editor-bg').trim() },
    });
    monaco.editor.setTheme('workbench-dark');
    instance.addAction({
      id: 'workbench.analyze',
      label: copy.actions.analyze,
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
      run: () => analyzeRef.current(),
    });
    instance.addAction({
      id: 'workbench.generate',
      label: copy.actions.generate,
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Shift | monaco.KeyCode.Enter],
      run: () => generateRef.current(),
    });
  };

  useEffect(() => {
    const instance = editorRef.current;
    const monaco = monacoRef.current;
    if (!instance || !monaco) return;
    const model = instance.getModel();
    if (model) monaco.editor.setModelMarkers(model, 'workbench-analysis', toMonacoMarkers(findings));
  }, [findings]);

  return (
    <Editor
      height="100%"
      language={language}
      value={value}
      theme="workbench-dark"
      onChange={(nextValue) => onChange(nextValue ?? '')}
      onMount={handleMount}
      options={{
        automaticLayout: true,
        minimap: { enabled: true },
        scrollBeyondLastLine: false,
        fontSize: 13,
        lineNumbers: 'on',
        tabSize: 2,
        wordWrap: 'on',
        renderValidationDecorations: 'on',
        accessibilitySupport: 'auto',
        ariaLabel: copy.accessibility.codeEditor,
      }}
    />
  );
}
