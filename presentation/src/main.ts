import '@fontsource-variable/fraunces/full.css';
import '@fontsource-variable/fraunces/full-italic.css';
import '@fontsource-variable/inter-tight/wght.css';
import 'katex/dist/katex.min.css';
import './styles.css';
import './chapters.css';
import { mountDeck, go } from './deck';
import { start, plan } from './api';
import { cover } from './chapters/cover';
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
import { engine } from './chapters/engine';
import { params } from './chapters/params';
import { interviewsChapter, hasInterviews } from './chapters/interviews';
import { missing } from './facts';

// "What students told us" joins the talk only when real interview material exists (it borrows time from II).
if (hasInterviews) problem.budget -= interviewsChapter.budget;
export const CHAPTERS = [cover, hook, problem, ...(hasInterviews ? [interviewsChapter] : []), how, demo, engine, params, robust, evidence, map, multicity, group, limits, close, math];
mountDeck(document.getElementById('deck')!, CHAPTERS);
void start();
// surfaced for the screenshot / digit checks
(window as any).__deck = { missing, chapters: CHAPTERS.map((c) => c.id), go, plan };
