import '@fontsource/playfair-display/400.css';
import '@fontsource/playfair-display/400-italic.css';
import '@fontsource-variable/inter';
import 'katex/dist/katex.min.css';
import './styles.css';
import './chapters.css';
import { mountDeck, go } from './deck';
import { start, plan } from './api';
import { cover } from './chapters/cover';
import { agenda } from './chapters/agenda';
import { hook } from './chapters/hook';
import { problem } from './chapters/problem';
import { how } from './chapters/how';
import { demo } from './chapters/demo';
import { robust } from './chapters/robust';
import { evidence } from './chapters/evidence';
import { map } from './chapters/map';
import { multicity } from './chapters/multicity';
import { group } from './chapters/group';
import { limits } from './chapters/limits';
import { close } from './chapters/close';
import { math } from './chapters/math';
import { missing } from './facts';

export const CHAPTERS = [cover, agenda, hook, problem, how, demo, robust, evidence, map, multicity, group, limits, close, math];
mountDeck(document.getElementById('deck')!, CHAPTERS);
void start();
// surfaced for the screenshot / digit checks
(window as any).__deck = { missing, chapters: CHAPTERS.map((c) => c.id), go, plan };
