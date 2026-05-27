import { useParams } from "react-router-dom";
import { TreeView } from "../components/TreeView";

export function TreePage() {
  const { spaceId } = useParams();
  return <TreeView spaceId={spaceId ?? null} />;
}
