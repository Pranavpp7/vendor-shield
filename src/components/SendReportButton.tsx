import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Mail, Loader2, CheckCircle2, XCircle } from "lucide-react";

interface SendReportButtonProps {
  assessmentId: string;
  vendorName?: string;
}

export function SendReportButton({ assessmentId, vendorName }: SendReportButtonProps) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [sentEmail, setSentEmail] = useState("");
  const [error, setError] = useState("");

  const handleSend = async () => {
    // Basic validation
    if (!email || !email.includes("@")) {
      setError("Please enter a valid email address.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      const res = await apiFetch("/api/email/send-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          assessment_id: assessmentId,
          recipient_email: email,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = Array.isArray(data.detail)
          ? data.detail[0]?.msg ?? `Request failed (${res.status})`
          : data.detail ?? `Request failed (${res.status})`;
        throw new Error(detail);
      }

      setSentEmail(email);
      setSuccess(true);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to send report";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (!newOpen) {
      // Reset state after the dialog closes
      setTimeout(() => {
        setEmail("");
        setLoading(false);
        setSuccess(false);
        setSentEmail("");
        setError("");
      }, 300);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" id="send-report-btn">
          <Mail className="h-4 w-4 mr-2" />
          Send Report
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-md">
        {success ? (
          /* ── Success State ────────────────────────────────────── */
          <div className="flex flex-col items-center py-8 gap-3">
            <CheckCircle2 className="h-12 w-12 text-green-500" />
            <h3 className="text-lg font-semibold">Report sent successfully!</h3>
            <p className="text-sm text-muted-foreground text-center">
              The PDF risk assessment report has been emailed to{" "}
              <span className="font-medium text-foreground">{sentEmail}</span>
            </p>
            <Button variant="outline" className="mt-4" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
          </div>
        ) : (
          /* ── Form State ───────────────────────────────────────── */
          <>
            <DialogHeader>
              <DialogTitle>Email Risk Report</DialogTitle>
              <DialogDescription>
                {vendorName
                  ? `Send the PDF assessment report for ${vendorName} to a recipient.`
                  : "Send the PDF assessment report to a recipient."}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="recipient-email">Recipient Email</Label>
                <Input
                  id="recipient-email"
                  type="email"
                  placeholder="stakeholder@company.com"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (error) setError("");
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !loading) handleSend();
                  }}
                  disabled={loading}
                  autoFocus
                />
              </div>

              {error && (
                <div className="flex items-center gap-2 text-sm text-red-500">
                  <XCircle className="h-4 w-4 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button
                variant="ghost"
                onClick={() => handleOpenChange(false)}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button onClick={handleSend} disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Sending…
                  </>
                ) : (
                  <>
                    <Mail className="h-4 w-4 mr-2" />
                    Send Report
                  </>
                )}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
