import { cx } from "../util.js";

export default function StatusPill({ status }) {
  return <span className={cx("pill", status)}>{status}</span>;
}
