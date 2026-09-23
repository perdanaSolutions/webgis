export type MenuTreeNode = {
  children?: MenuTreeNode[];
};

export function flattenMenuTree<T extends MenuTreeNode>(
  items: T[] | null | undefined,
): T[] {
  const result: T[] = [];
  for (const item of items ?? []) {
    result.push(item);
    if (item.children?.length) {
      result.push(...flattenMenuTree(item.children as T[]));
    }
  }
  return result;
}

export function menuSubtreeDepth<T extends MenuTreeNode>(node: T | null | undefined): number {
  if (!node?.children?.length) return 0;
  return 1 + Math.max(...node.children.map((child) => menuSubtreeDepth(child as T)));
}
