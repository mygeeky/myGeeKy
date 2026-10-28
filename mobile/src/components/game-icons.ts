// The games' icons (tools/game_icons.py cuts them from one sheet; the desktop has the same in gui/assets/game_*.png),
// and the Games entry's own picture, GeeKOc playing (hub), which the menu draws instead of a line icon.
import type { ImageSourcePropType } from 'react-native';

const ICONS: Record<string, ImageSourcePropType> = {
  hub: require('../../assets/games/hub.png'),
  hunter: require('../../assets/games/hunter.png'), rise: require('../../assets/games/rise.png'),
  maze: require('../../assets/games/maze.png'), run: require('../../assets/games/run.png'),
  flappy: require('../../assets/games/flappy.png'), whack: require('../../assets/games/whack.png'),
  realfake: require('../../assets/games/realfake.png'), genemon: require('../../assets/games/genemon.png'),
  reviewer: require('../../assets/games/reviewer.png'), reef: require('../../assets/games/reef.png'),
  catch: require('../../assets/games/catch.png'), figure: require('../../assets/games/figure.png'),
  first: require('../../assets/games/first.png'), terminal: require('../../assets/games/terminal.png'),
};
export const gameIcon = (id: string) => ICONS[id] ?? ICONS.hub;
