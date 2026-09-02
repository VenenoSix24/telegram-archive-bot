// 单一来源仍是 pyproject.toml；构建时从这里同步（package.json 由发布流程对齐）。
import pkg from '../../package.json'

export const APP_VERSION: string = pkg.version
