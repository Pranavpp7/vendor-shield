import { Assessment } from "@/types/assessment";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { RiskBadge } from "./RiskBadge";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assessments: Assessment[];
};

export function CompareModal({ open, onOpenChange, assessments }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Vendor Comparison</DialogTitle>
        </DialogHeader>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2 font-medium">Metric</th>
                {assessments.map((a) => (
                  <th key={a.id} className="text-left py-2 font-medium">{a.vendorName}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="border-b">
                <td className="py-2 text-muted-foreground">Score</td>
                {assessments.map((a) => (
                  <td key={a.id} className="py-2 font-semibold">{a.score}/100</td>
                ))}
              </tr>
              <tr className="border-b">
                <td className="py-2 text-muted-foreground">Risk Level</td>
                {assessments.map((a) => (
                  <td key={a.id} className="py-2"><RiskBadge level={a.riskLevel} /></td>
                ))}
              </tr>
              <tr className="border-b">
                <td className="py-2 text-muted-foreground">Passed Controls</td>
                {assessments.map((a) => (
                  <td key={a.id} className="py-2 text-risk-low font-medium">
                    {a.controls.filter((c) => c.passed).length}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="py-2 text-muted-foreground">Failed Controls</td>
                {assessments.map((a) => (
                  <td key={a.id} className="py-2 text-risk-high font-medium">
                    {a.controls.filter((c) => !c.passed).length}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </DialogContent>
    </Dialog>
  );
}
