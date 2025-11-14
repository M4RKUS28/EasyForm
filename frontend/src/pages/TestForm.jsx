import { useState } from "react";
import { Link } from "react-router-dom";
import Header from "../components/Header";
import "./TestForm.css";

const mathPrompts = [
  { id: "mathQ1", label: "1) 18 + 27 = ?", placeholder: "Type the result" },
  { id: "mathQ2", label: "2) 96 / 3 = ?", placeholder: "Type the result" },
  {
    id: "mathQ3",
    label: "3) A project team has 4 analysts. Each analyst assists 6 enterprise clients. How many clients are covered in total?",
    placeholder: "Explain your reasoning or give the number"
  }
];

const cvPrompts = [
  {
    id: "cvQ1",
    label: "State your full name and current job title exactly as they appear on your CV."
  },
  {
    id: "cvQ2",
    label: "Which school or university did you graduate from, and which degree did you earn?"
  },
  {
    id: "cvQ3",
    label: "Highlight one measurable accomplishment from your CV (include numbers, percentages, or timelines)."
  },
  {
    id: "cvQ4",
    label: "List the tools or platforms you are most comfortable using on a daily basis."
  }
];

function TestForm() {
  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    mathQ1: "",
    mathQ2: "",
    mathQ3: "",
    mathExplanation: "",
    cvQ1: "",
    cvQ2: "",
    cvQ3: "",
    cvQ4: "",
    cvSummary: "",
    agree: false
  });

  const handleChange = (event) => {
    const { name, value, type, checked } = event.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value
    }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    console.log("Math & CV test submitted:", formData);
    alert("Responses submitted. Check the console for the payload.");
  };

  return (
    <div className="test-form-page">
      <Header />
      <div className="test-form-container">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1>Addon Test Form</h1>
            <p className="form-description">
              Practice answering deterministic math questions and general knowledge checks that reference a candidate CV.
            </p>
            <p className="mt-3 text-sm font-semibold text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2 text-center">
              After installing the extension, please reload every page (including this one) once so EasyForm can run properly.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="test-form">
          <section className="form-section">
            <h2>Participant</h2>
            <div className="form-group">
              <label htmlFor="fullName">Full Name *</label>
              <input
                id="fullName"
                name="fullName"
                type="text"
                value={formData.fullName}
                onChange={handleChange}
                required
                placeholder="Alex Example"
              />
            </div>
            <div className="form-group">
              <label htmlFor="email">Email *</label>
              <input
                id="email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                required
                placeholder="alex@example.com"
              />
            </div>
          </section>

          <section className="form-section">
            <h2>Math Questions</h2>
            {mathPrompts.map((prompt) => (
              <div className="form-group" key={prompt.id}>
                <label htmlFor={prompt.id}>{prompt.label}</label>
                <input
                  id={prompt.id}
                  name={prompt.id}
                  type="text"
                  placeholder={prompt.placeholder}
                  value={formData[prompt.id]}
                  onChange={handleChange}
                  required
                />
              </div>
            ))}
            <div className="form-group">
              <label htmlFor="mathExplanation">
                Optional: explain one of your calculations or share a quick verification step
              </label>
              <textarea
                id="mathExplanation"
                name="mathExplanation"
                rows="3"
                value={formData.mathExplanation}
                onChange={handleChange}
                placeholder="Show how you approached one of the problems."
              />
            </div>
          </section>

          <section className="form-section">
            <h2>User Questions Based on the CV</h2>
            {cvPrompts.map((prompt) => (
              <div className="form-group" key={prompt.id}>
                <label htmlFor={prompt.id}>{prompt.label}</label>
                <textarea
                  id={prompt.id}
                  name={prompt.id}
                  rows="3"
                  value={formData[prompt.id]}
                  onChange={handleChange}
                  required
                  placeholder="Your answer..."
                />
              </div>
            ))}
            <div className="form-group">
              <label htmlFor="cvSummary">
                Final check: In 2-3 sentences, summarize why your CV makes you a fit for the next interview round.
              </label>
              <textarea
                id="cvSummary"
                name="cvSummary"
                rows="4"
                value={formData.cvSummary}
                onChange={handleChange}
                required
                placeholder="Provide a concise recommendation referencing the CV details."
              />
            </div>
          </section>

          <section className="form-section">
            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  name="agree"
                  checked={formData.agree}
                  onChange={handleChange}
                  required
                />
                I confirm the above answers are my own work. *
              </label>
            </div>
          </section>

          <div className="form-actions">
            <button type="submit" className="submit-button">
              Submit Form
            </button>
            <button type="button" className="reset-button" onClick={() => window.location.reload()}>
              Reset
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default TestForm;
