export interface ControlPlanOption {
  id: string;
  label: string;
  detail?: string;
  selected?: boolean;
}

/** One checkbox per protocol ID. A conflicting ID cannot be disambiguated by option_ids. */
export function normalizeControlPlanOptions(options: ControlPlanOption[]): ControlPlanOption[] {
  const unique = new Map<string, ControlPlanOption>();
  for (const option of options) {
    if (!option || typeof option.id !== 'string' || !option.id.trim() || typeof option.label !== 'string'
      || (option.detail !== undefined && typeof option.detail !== 'string')) throw new Error('Control Plan 候选选项格式不正确');
    const previous = unique.get(option.id);
    if (previous) {
      if (previous.label.trim() !== option.label.trim() || (previous.detail ?? '').trim() !== (option.detail ?? '').trim()) {
        throw new Error('Control Plan 服务返回了相同标识但名称或来源不同的候选，无法独立勾选，请重新查询或联系服务维护人员修正选项标识。');
      }
      unique.set(option.id, { ...previous, selected: previous.selected === true || option.selected === true });
    } else unique.set(option.id, { ...option });
  }
  return [...unique.values()];
}

/** Toggle only matching candidates; keep deliberate selections outside the search. */
export function toggleMatchingOptions(selected: string[], matching: string[]): string[] {
  const ids = new Set(matching);
  if (!ids.size) return selected;
  return matching.every(id => selected.includes(id))
    ? selected.filter(id => !ids.has(id))
    : [...new Set([...selected, ...matching])];
}
