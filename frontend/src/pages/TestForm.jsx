import { useState } from 'react';
import Header from '../components/Header';
import './TestForm.css';

function TestForm() {
  const [formData, setFormData] = useState({
    // Personal Information
    firstName: '',
    lastName: '',
    email: '',
    age: '',
    gender: '',
    
    // Address
    street: '',
    city: '',
    zipCode: '',
    country: '',
    
    // Business Ethics Quiz
    ethicsQ1: '',
    ethicsQ2: [],
    ethicsQ3: '',
    ethicsQ4: '',
    ethicsQ5: '',
    ethicsQ6: '',
    ethicsQ7: '',
    ethicsQ8: '',
    ethicsQ9: '',
    ethicsQ10: '',


    ethicsQ15: '',
    ethicsQ16: [], // Wichtig: Leeres Array für Multiple-Choice
    ethicsQ17: '',
    ethicsQ18: '',
    ethicsQ19: '',
    ethicsQ20: '',
    ethicsQ21: '',
    ethicsQ22: [], // Wichtig: Leeres Array für Multiple-Choice
    ethicsQ23: '',
    ethicsQ24: '',
    ethicsQ25: '',
    ethicsQ26: '',
    ethicsQ27: '',
    ethicsQ28: '',
    ethicsQ29: [], // Wichtig: Leeres Array für Multiple-Choice
    ethicsQ30: '',
    
    // Additional
    bio: '',
    rating: '5',
    agree: false
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    
    if (type === 'checkbox' && name === 'ethicsQ2') {
      setFormData(prev => ({
        ...prev,
        ethicsQ2: checked 
          ? [...prev.ethicsQ2, value]
          : prev.ethicsQ2.filter(h => h !== value)
      }));
    } else if (type === 'checkbox') {
      setFormData(prev => ({ ...prev, [name]: checked }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log('Form submitted:', formData);
    alert('Form successfully submitted! Check the console for details.');
  };

  return (
    <div className="test-form-page">
      <Header />
      <div className="test-form-container">
        <h1>Addon Test Form</h1>
        <p className="form-description">
          This form is designed to test the browser addon with various input types.
        </p>
        
        <form onSubmit={handleSubmit} className="test-form">
          {/* Personal Information Section */}
          <section className="form-section">
            <h2>Personal Information</h2>
            
            <div className="form-group">
              <label htmlFor="firstName">First Name *</label>
              <input
                type="text"
                id="firstName"
                name="firstName"
                value={formData.firstName}
                onChange={handleChange}
                required
                placeholder="John"
              />
            </div>

            <div className="form-group">
              <label htmlFor="lastName">Last Name *</label>
              <input
                type="text"
                id="lastName"
                name="lastName"
                value={formData.lastName}
                onChange={handleChange}
                required
                placeholder="Doe"
              />
            </div>

            <div className="form-group">
              <label htmlFor="email">Email Address *</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                required
                placeholder="john@example.com"
              />
            </div>

            <div className="form-group">
              <label htmlFor="age">Age</label>
              <input
                type="number"
                id="age"
                name="age"
                value={formData.age}
                onChange={handleChange}
                min="0"
                max="120"
                placeholder="25"
              />
            </div>

            <div className="form-group">
              <label>Gender</label>
              <div className="radio-group">
                <label className="radio-label">
                  <input
                    type="radio"
                    name="gender"
                    value="male"
                    checked={formData.gender === 'male'}
                    onChange={handleChange}
                  />
                  Male
                </label>
                <label className="radio-label">
                  <input
                    type="radio"
                    name="gender"
                    value="female"
                    checked={formData.gender === 'female'}
                    onChange={handleChange}
                  />
                  Female
                </label>
                <label className="radio-label">
                  <input
                    type="radio"
                    name="gender"
                    value="other"
                    checked={formData.gender === 'other'}
                    onChange={handleChange}
                  />
                  Other
                </label>
              </div>
            </div>
          </section>

          {/* Address Section */}
          <section className="form-section">
            <h2>Address</h2>
            
            <div className="form-group">
              <label htmlFor="street">Street Address</label>
              <input
                type="text"
                id="street"
                name="street"
                value={formData.street}
                onChange={handleChange}
                placeholder="123 Main Street"
              />
            </div>

            <div className="form-group">
              <label htmlFor="city">City</label>
              <input
                type="text"
                id="city"
                name="city"
                value={formData.city}
                onChange={handleChange}
                placeholder="New York"
              />
            </div>

            <div className="form-group">
              <label htmlFor="zipCode">ZIP Code</label>
              <input
                type="text"
                id="zipCode"
                name="zipCode"
                value={formData.zipCode}
                onChange={handleChange}
                placeholder="10001"
              />
            </div>

            <div className="form-group">
              <label htmlFor="country">Country</label>
              <select
                id="country"
                name="country"
                value={formData.country}
                onChange={handleChange}
              >
                <option value="">Please select...</option>
                <option value="DE">Germany</option>
                <option value="AT">Austria</option>
                <option value="CH">Switzerland</option>
                <option value="US">USA</option>
                <option value="GB">United Kingdom</option>
                <option value="FR">France</option>
              </select>
            </div>
          </section>
          
          {/* Business Ethics Quiz Section */}
          <section className="form-section">
            <h2>Business Ethics Quiz</h2>
            
            <div className="form-group">
                <label>Question 1: Which ethical theory focuses on "the greatest good for the greatest number of people"?</label>
                <div className="radio-group">
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ1" value="virtue" checked={formData.ethicsQ1 === 'virtue'} onChange={handleChange} />
                        Virtue Ethics
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ1" value="utilitarianism" checked={formData.ethicsQ1 === 'utilitarianism'} onChange={handleChange} />
                        Utilitarianism (correct)
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ1" value="universal" checked={formData.ethicsQ1 === 'universal'} onChange={handleChange} />
                        Universal Ethics
                    </label>
                </div>
            </div>

            <div className="form-group">
                <label>Question 2: According to the presentation, who are considered stakeholders in a business enterprise? (select multiple)</label>
                <div className="checkbox-group">
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ2" value="employees" checked={formData.ethicsQ2.includes('employees')} onChange={handleChange} />
                        Employees (correct)
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ2" value="customers" checked={formData.ethicsQ2.includes('customers')} onChange={handleChange} />
                        Customers (correct)
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ2" value="competitors" checked={formData.ethicsQ2.includes('competitors')} onChange={handleChange} />
                        Competitors
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ2" value="community" checked={formData.ethicsQ2.includes('community')} onChange={handleChange} />
                        Community (correct)
                    </label>
                </div>
            </div>

            <div className="form-group">
                <label>Question 3: The Sarbanes-Oxley Act of 2002 was a business ethics development that primarily targeted what?</label>
                <div className="radio-group">
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ3" value="environment" checked={formData.ethicsQ3 === 'environment'} onChange={handleChange} />
                        Environmental protection
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ3" value="workplace_safety" checked={formData.ethicsQ3 === 'workplace_safety'} onChange={handleChange} />
                        Workplace safety
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ3" value="accountability" checked={formData.ethicsQ3 === 'accountability'} onChange={handleChange} />
                        Greater accountability for chief executives and boards of directors (correct)
                    </label>
                </div>
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ4">Question 4: What is the "Golden Rule" in ethics? (1-2 sentences)</label>
              <input
                type="text"
                id="ethicsQ4"
                name="ethicsQ4"
                value={formData.ethicsQ4}
                onChange={handleChange}
                placeholder="Your answer"
              />
              <small className="hint">Correct answer: Do unto others as you would have them do unto you.</small>
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ5">Question 5: What is a primary myth about ethics discussed in the presentation?</label>
              <input
                type="text"
                id="ethicsQ5"
                name="ethicsQ5"
                value={formData.ethicsQ5}
                onChange={handleChange}
                placeholder="Your answer"
              />
              <small className="hint">Acceptable answers: "We learn ethics as kids and it's too late now," "Sitting in class doesn't change behavior," or "We already know what's right."</small>
            </div>

             <div className="form-group">
              <label htmlFor="ethicsQ6">Question 6: In 1-3 sentences, explain the concept of an "ethical dilemma".</label>
              <textarea
                id="ethicsQ6"
                name="ethicsQ6"
                value={formData.ethicsQ6}
                onChange={handleChange}
                rows="3"
                placeholder="Explain the concept..."
              />
              <small className="hint">A situation with no obvious right or wrong answer, but rather a conflict between two 'right' choices or values.</small>
            </div>
            
            <div className="form-group">
                <label>Question 7: At which level of Kohlberg's Stages of Moral Development is an individual's reasoning self-centered and focused on external consequences like punishment?</label>
                <div className="radio-group">
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ7" value="pre" checked={formData.ethicsQ7 === 'pre'} onChange={handleChange} />
                        Level 1: Pre-Conventional Morality (correct)
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ7" value="con" checked={formData.ethicsQ7 === 'con'} onChange={handleChange} />
                        Level 2: Conventional Morality
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ7" value="post" checked={formData.ethicsQ7 === 'post'} onChange={handleChange} />
                        Level 3: Post-Conventional Morality
                    </label>
                </div>
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ8">Question 8: Briefly describe one common rationalization for unethical behavior mentioned in the text.</label>
              <input
                type="text"
                id="ethicsQ8"
                name="ethicsQ8"
                value={formData.ethicsQ8}
                onChange={handleChange}
                placeholder="Your answer"
              />
              <small className="hint">E.g., "The activity is not 'really' illegal," "It's in the corporation's best interests," "It will never be found out," "The company will protect me."</small>
            </div>

            <div className="form-group">
                <label>Question 9: What is the core idea of Universal Ethics (also known as Deontology)?</label>
                <div className="radio-group">
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ9" value="consequences" checked={formData.ethicsQ9 === 'consequences'} onChange={handleChange} />
                        The morality of an act is determined by its outcome.
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ9" value="character" checked={formData.ethicsQ9 === 'character'} onChange={handleChange} />
                        The cultivation of virtuous character traits is fundamental to ethical behavior.
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ9" value="duty" checked={formData.ethicsQ9 === 'duty'} onChange={handleChange} />
                        Certain ethical principles are absolute and apply to all, and morality is determined by adherence to duties/rules. (correct)
                    </label>
                </div>
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ10">Question 10: In your own words (1-3 sentences), why is it often said that "business ethics" can be an oxymoron?</label>
              <textarea
                id="ethicsQ10"
                name="ethicsQ10"
                value={formData.ethicsQ10}
                onChange={handleChange}
                rows="3"
                placeholder="Explain the apparent contradiction..."
              />
               <small className="hint">Because the primary goal of business (profit maximization) can often conflict with ethical principles and considerations.</small>
            </div>
          </section>

          {/* Additional Section */}
          <section className="form-section">
            <h2>Additional Information</h2>
            
            <div className="form-group">
              <label htmlFor="bio">About You (Biography)</label>
              <textarea
                id="bio"
                name="bio"
                value={formData.bio}
                onChange={handleChange}
                rows="5"
                placeholder="Tell us something about yourself..."
              />
            </div>

            <div className="form-group">
              <label htmlFor="rating">How satisfied are you? (1-10)</label>
              <input
                type="range"
                id="rating"
                name="rating"
                value={formData.rating}
                onChange={handleChange}
                min="1"
                max="10"
              />
              <span className="range-value">{formData.rating}/10</span>
            </div>

            {/* START: HIER DEN NEUEN JSX-CODE EINFÜGEN */}

            <div className="form-group">
                <label>Question 15: Auf welcher Stufe von Kohlbergs moralischer Entwicklung basieren Entscheidungen auf selbstgewählten, universellen ethischen Prinzipien, selbst wenn diese im Konflikt mit dem Gesetz stehen?</label>
                <div className="radio-group">
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ15" value="conventional" checked={formData.ethicsQ15 === 'conventional'} onChange={handleChange} />
                        Level 2: Conventional Morality
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ15" value="pre-conventional" checked={formData.ethicsQ15 === 'pre-conventional'} onChange={handleChange} />
                        Level 1: Pre-Conventional Morality
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ15" value="post-conventional" checked={formData.ethicsQ15 === 'post-conventional'} onChange={handleChange} />
                        Level 3: Post-Conventional Morality
                    </label>
                </div>
            </div>

            <div className="form-group">
                <label>Question 16: Welche der folgenden Aussagen sind laut den Unterlagen Mythen über Ethik? (Mehrfachauswahl möglich)</label>
                <div className="checkbox-group">
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ16" value="childhood" checked={formData.ethicsQ16.includes('childhood')} onChange={handleChange} />
                        Ethik wird ausschließlich in der Kindheit gelernt und kann später nicht mehr verändert werden.
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ16" value="maturity" checked={formData.ethicsQ16.includes('maturity')} onChange={handleChange} />
                        Ethische Reife kann sich im Laufe des Lebens eines Menschen entwickeln und wachsen.
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ16" value="opinion" checked={formData.ethicsQ16.includes('opinion')} onChange={handleChange} />
                        Ethik ist lediglich eine Frage der persönlichen Meinung und hat keine objektive Grundlage.
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ16" value="behavior" checked={formData.ethicsQ16.includes('behavior')} onChange={handleChange} />
                        Ethische Bildung hat keinen Einfluss auf das tatsächliche Verhalten einer Person.
                    </label>
                </div>
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ17">Question 17: Welches ethische Prinzip, das von Aristoteles stammt, konzentriert sich auf die Entwicklung des Charakters und das Streben nach einem idealen Selbst?</label>
              <input
                type="text"
                id="ethicsQ17"
                name="ethicsQ17"
                value={formData.ethicsQ17}
                onChange={handleChange}
                placeholder="Name der ethischen Theorie"
              />
            </div>

            <div className="form-group">
                <label>Question 18: Die "Federal Sentencing Guidelines" (1991) waren eine wichtige Entwicklung in der Geschichte der Wirtschaftsethik. Was war ihr Hauptzweck?</label>
                <div className="radio-group">
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ18" value="child_labor" checked={formData.ethicsQ18 === 'child_labor'} onChange={handleChange} />
                        Verbot von Kinderarbeit in Drittweltländern.
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ18" value="mandate" checked={formData.ethicsQ18 === 'mandate'} onChange={handleChange} />
                        Einführung stärkerer ethischer Schutzmaßnahmen für Organisationen.
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ18" value="ceo_pay" checked={formData.ethicsQ18 === 'ceo_pay'} onChange={handleChange} />
                        Regulierung der Gehälter von CEOs.
                    </label>
                </div>
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ19">Question 19: Erklären Sie in 1-2 Sätzen den Unterschied zwischen intrinsischen und instrumentellen Werten.</label>
              <textarea
                id="ethicsQ19"
                name="ethicsQ19"
                value={formData.ethicsQ19}
                onChange={handleChange}
                rows="2"
                placeholder="Ihre Erklärung..."
              />
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ20">Question 20: Was versteht man unter dem Begriff "Corporate Governance"?</label>
              <textarea
                id="ethicsQ20"
                name="ethicsQ20"
                value={formData.ethicsQ20}
                onChange={handleChange}
                rows="3"
                placeholder="Definieren Sie den Begriff..."
              />
            </div>

            <div className="form-group">
                <label>Question 21: Welche der folgenden Philosophien argumentiert, dass Moral aus dem Zweck oder "Telos" des Menschen abgeleitet wird?</label>
                <div className="radio-group">
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ21" value="natural_law" checked={formData.ethicsQ21 === 'natural_law'} onChange={handleChange} />
                        Natural Law Theory
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ21" value="rights_based" checked={formData.ethicsQ21 === 'rights_based'} onChange={handleChange} />
                        Rights-Based Theories
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ21" value="utilitarianism" checked={formData.ethicsQ21 === 'utilitarianism'} onChange={handleChange} />
                        Utilitarianism
                    </label>
                </div>
            </div>

            <div className="form-group">
                <label>Question 22: Welche der folgenden Punkte gehören zu den drei Prinzipien zur Auflösung eines ethischen Dilemmas? (Mehrfachauswahl möglich)</label>
                <div className="checkbox-group">
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ22" value="ends_based" checked={formData.ethicsQ22.includes('ends_based')} onChange={handleChange} />
                        'Ends-Based' (Ergebnisbasiert)
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ22" value="profit_based" checked={formData.ethicsQ22.includes('profit_based')} onChange={handleChange} />
                        'Profit-Based' (Profitbasiert)
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ22" value="golden_rule" checked={formData.ethicsQ22.includes('golden_rule')} onChange={handleChange} />
                        'The Golden Rule' (Die Goldene Regel)
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ22" value="rules_based" checked={formData.ethicsQ22.includes('rules_based')} onChange={handleChange} />
                        'Rules-Based' (Regelbasiert)
                    </label>
                </div>
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ23">Question 23: Was bedeutet das Akronym GAAP und welche Rolle spielt es im Rechnungswesen?</label>
              <input
                type="text"
                id="ethicsQ23"
                name="ethicsQ23"
                value={formData.ethicsQ23}
                onChange={handleChange}
                placeholder="Akronym und Rolle..."
              />
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ24">Question 24: Ein Manager bittet einen Mitarbeiter, die Verkaufszahlen zu "beschönigen", um die Quartalsziele zu erreichen. Beschreiben Sie zwei gängige Rationalisierungen, die der Manager oder Mitarbeiter zur Rechtfertigung dieser Handlung verwenden könnte.</label>
              <textarea
                id="ethicsQ24"
                name="ethicsQ24"
                value={formData.ethicsQ24}
                onChange={handleChange}
                rows="3"
                placeholder="Beschreiben Sie zwei Rationalisierungen..."
              />
            </div>
            
            <div className="form-group">
                <label>Question 25: Aristoteles' "Lehre von der Mitte" (Doctrine of the Mean) besagt, dass eine Tugend zwischen zwei Extremen liegt. Diese Extreme sind...</label>
                <div className="radio-group">
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ25" value="good_evil" checked={formData.ethicsQ25 === 'good_evil'} onChange={handleChange} />
                        Gut und Böse
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ25" value="excess_deficiency" checked={formData.ethicsQ25 === 'excess_deficiency'} onChange={handleChange} />
                        Übermaß und Mangel
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ25" value="right_wrong" checked={formData.ethicsQ25 === 'right_wrong'} onChange={handleChange} />
                        Richtig und Falsch
                    </label>
                </div>
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ26">Question 26: Nennen Sie zwei Beispiele, wie unethische Finanzberichterstattung die Mitarbeiter eines Unternehmens negativ beeinflussen kann.</label>
              <input
                type="text"
                id="ethicsQ26"
                name="ethicsQ26"
                value={formData.ethicsQ26}
                onChange={handleChange}
                placeholder="Zwei Beispiele..."
              />
            </div>
            
            <div className="form-group">
                <label>Question 27: Wie lautet der Name von Kants universellem Test für moralisches Handeln?</label>
                <div className="radio-group">
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ27" value="golden_rule" checked={formData.ethicsQ27 === 'golden_rule'} onChange={handleChange} />
                        Die Goldene Regel
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ27" value="categorical_imperative" checked={formData.ethicsQ27 === 'categorical_imperative'} onChange={handleChange} />
                        Der Kategorische Imperativ
                    </label>
                    <label className="radio-label">
                        <input type="radio" name="ethicsQ27" value="principle_utility" checked={formData.ethicsQ27 === 'principle_utility'} onChange={handleChange} />
                        Das Nützlichkeitsprinzip
                    </label>
                </div>
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ28">Question 28: Was war das zentrale ethische Dilemma im Fall des Ford Pinto bezüglich des Designs des Kraftstofftanks?</label>
              <textarea
                id="ethicsQ28"
                name="ethicsQ28"
                value={formData.ethicsQ28}
                onChange={handleChange}
                rows="3"
                placeholder="Beschreiben Sie das Dilemma..."
              />
            </div>
            
            <div className="form-group">
                <label>Question 29: Warum sollte die Personalabteilung (HR) laut den Unterlagen eine zentrale Rolle in einem Ethikkodex des Unternehmens spielen? (Mehrfachauswahl möglich)</label>
                <div className="checkbox-group">
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ29" value="payroll" checked={formData.ethicsQ29.includes('payroll')} onChange={handleChange} />
                        Sie sind für die Gehaltsabrechnung zuständig.
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ29" value="leadership" checked={formData.ethicsQ29.includes('leadership')} onChange={handleChange} />
                        Sie stellen sicher, dass die Auswahl von Führungskräften eine Ethikkomponente beinhaltet.
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ29" value="legislation" checked={formData.ethicsQ29.includes('legislation')} onChange={handleChange} />
                        Sie bleiben über sich ändernde Ethikgesetze auf dem Laufenden.
                    </label>
                    <label className="checkbox-label">
                        <input type="checkbox" name="ethicsQ29" value="picnics" checked={formData.ethicsQ29.includes('picnics')} onChange={handleChange} />
                        Sie organisieren die Firmenpicknicks.
                    </label>
                </div>
            </div>

            <div className="form-group">
              <label htmlFor="ethicsQ30">Question 30: Erklären Sie den 'Profit Maximization Imperative' und wie er zu Spannungen mit ethischem Verhalten führen kann.</label>
              <textarea
                id="ethicsQ30"
                name="ethicsQ30"
                value={formData.ethicsQ30}
                onChange={handleChange}
                rows="3"
                placeholder="Erklären Sie die Spannung..."
              />
            </div>

            {/* ENDE: HIER DEN NEUEN JSX-CODE EINFÜGEN */}

            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  name="agree"
                  checked={formData.agree}
                  onChange={handleChange}
                  required
                />
                I agree to the terms and conditions *
              </label>
            </div>
          </section>

          {/* Submit Button */}
          <div className="form-actions">
            <button type="submit" className="submit-button">
              Submit Form
            </button>
            <button 
              type="button" 
              className="reset-button"
              onClick={() => window.location.reload()}
            >
              Reset
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default TestForm;