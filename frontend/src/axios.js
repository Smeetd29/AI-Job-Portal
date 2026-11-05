import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '',
    withCredentials: true,
    headers: { 'Content-Type': 'application/json' },
});

api.defaults.xsrfCookieName = 'csrftoken';
api.defaults.xsrfHeaderName = 'X-CSRFToken';

let csrfPromise = null;

export function getCookie(name) {
    if (typeof document === 'undefined' || !document.cookie) return null;
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.startsWith(name + '=')) {
            return decodeURIComponent(cookie.substring(name.length + 1));
        }
    }
    return null;
}

export async function ensureCsrf() {
    let token = getCookie('csrftoken');
    if (token) return token;

    if (!csrfPromise) {
        csrfPromise = api
            .get('/api/csrf/', { withCredentials: true })
            .then((res) => res.data?.csrfToken || getCookie('csrftoken'))
            .catch(() => null)
            .finally(() => {
                csrfPromise = null;
            });
    }
    return csrfPromise;
}

api.interceptors.request.use(async (config) => {
    const isMutation = ['post', 'put', 'patch', 'delete'].includes(config.method?.toLowerCase());
    let csrfToken = getCookie('csrftoken');

    if (isMutation && !csrfToken) {
        csrfToken = await ensureCsrf();
    }

    if (csrfToken) {
        config.headers['X-CSRFToken'] = csrfToken;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        const requestUrl = error.config?.url || '';
        const isAuthRequest = requestUrl.includes('/api/login/') || requestUrl.includes('/api/signup/');
        if (error.response?.status === 401 && !isAuthRequest) {
            window.dispatchEvent(new Event('auth:unauthorized'));
        }
        return Promise.reject(error);
    }
);

export default api;
