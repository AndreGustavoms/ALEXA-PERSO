import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from '@/App';
import '@/app/globals.css';

const root = document.getElementById('root');

if (!root) {
  throw new Error('O elemento principal da interface não foi encontrado.');
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
