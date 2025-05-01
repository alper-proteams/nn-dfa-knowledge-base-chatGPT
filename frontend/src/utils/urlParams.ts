/**
 * Extracts query parameters from the URL
 * @returns An object containing all query parameters
 */
export const getQueryParams = (): Record<string, string> => {
  const params = new URLSearchParams(window.location.search);
  const result: Record<string, string> = {};
  
  for (const [key, value] of params.entries()) {
    result[key] = value;
  }
  
  return result;
};

/**
 * Gets a specific query parameter from the URL
 * @param name The name of the query parameter
 * @returns The value of the query parameter or null if not found
 */
export const getQueryParam = (name: string): string | null => {
  const url = window.location.href;
  console.log('Current URL:', url);
  const params = new URLSearchParams(window.location.search);
  const value = params.get(name);
  console.log(`URL param "${name}" value:`, value);
  return value;
};
