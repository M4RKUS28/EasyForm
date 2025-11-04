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
    
    // Preferences
    favoriteColor: '',
    hobbies: [],
    newsletter: false,
    
    // Math Questions
    mathAnswer1: '',
    mathAnswer2: '',
    mathAnswer3: '',
    
    // English Questions
    englishAnswer1: '',
    englishAnswer2: '',
    englishAnswer3: '',
    
    // Additional
    bio: '',
    rating: '5',
    agree: false
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    
    if (type === 'checkbox' && name === 'hobbies') {
      setFormData(prev => ({
        ...prev,
        hobbies: checked 
          ? [...prev.hobbies, value]
          : prev.hobbies.filter(h => h !== value)
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

          {/* Preferences Section */}
          <section className="form-section">
            <h2>Preferences</h2>
            
            <div className="form-group">
              <label htmlFor="favoriteColor">Favorite Color</label>
              <input
                type="color"
                id="favoriteColor"
                name="favoriteColor"
                value={formData.favoriteColor || '#3498db'}
                onChange={handleChange}
              />
            </div>

            <div className="form-group">
              <label>Hobbies (select multiple)</label>
              <div className="checkbox-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    name="hobbies"
                    value="reading"
                    checked={formData.hobbies.includes('reading')}
                    onChange={handleChange}
                  />
                  Reading
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    name="hobbies"
                    value="sports"
                    checked={formData.hobbies.includes('sports')}
                    onChange={handleChange}
                  />
                  Sports
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    name="hobbies"
                    value="music"
                    checked={formData.hobbies.includes('music')}
                    onChange={handleChange}
                  />
                  Music
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    name="hobbies"
                    value="gaming"
                    checked={formData.hobbies.includes('gaming')}
                    onChange={handleChange}
                  />
                  Gaming
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    name="hobbies"
                    value="cooking"
                    checked={formData.hobbies.includes('cooking')}
                    onChange={handleChange}
                  />
                  Cooking
                </label>
              </div>
            </div>

            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  name="newsletter"
                  checked={formData.newsletter}
                  onChange={handleChange}
                />
                Subscribe to newsletter
              </label>
            </div>
          </section>

          {/* Math Quiz Section */}
          <section className="form-section">
            <h2>Math Quiz</h2>
            
            <div className="form-group">
              <label htmlFor="mathAnswer1">Question 1: What is 15 + 27?</label>
              <input
                type="number"
                id="mathAnswer1"
                name="mathAnswer1"
                value={formData.mathAnswer1}
                onChange={handleChange}
                placeholder="Your answer"
              />
              <small className="hint">Correct answer: 42</small>
            </div>

            <div className="form-group">
              <label htmlFor="mathAnswer2">Question 2: What is 8 × 7?</label>
              <input
                type="number"
                id="mathAnswer2"
                name="mathAnswer2"
                value={formData.mathAnswer2}
                onChange={handleChange}
                placeholder="Your answer"
              />
              <small className="hint">Correct answer: 56</small>
            </div>

            <div className="form-group">
              <label htmlFor="mathAnswer3">Question 3: What is the square root of 144?</label>
              <input
                type="number"
                id="mathAnswer3"
                name="mathAnswer3"
                value={formData.mathAnswer3}
                onChange={handleChange}
                placeholder="Your answer"
              />
              <small className="hint">Correct answer: 12</small>
            </div>
          </section>

          {/* English Quiz Section */}
          <section className="form-section">
            <h2>English Questions</h2>
            
            <div className="form-group">
              <label>Question 1: What is the past tense of "go"?</label>
              <div className="radio-group">
                <label className="radio-label">
                  <input
                    type="radio"
                    name="englishAnswer1"
                    value="goed"
                    checked={formData.englishAnswer1 === 'goed'}
                    onChange={handleChange}
                  />
                  goed
                </label>
                <label className="radio-label">
                  <input
                    type="radio"
                    name="englishAnswer1"
                    value="went"
                    checked={formData.englishAnswer1 === 'went'}
                    onChange={handleChange}
                  />
                  went (correct)
                </label>
                <label className="radio-label">
                  <input
                    type="radio"
                    name="englishAnswer1"
                    value="gone"
                    checked={formData.englishAnswer1 === 'gone'}
                    onChange={handleChange}
                  />
                  gone
                </label>
              </div>
            </div>

            <div className="form-group">
              <label>Question 2: Which word is a noun?</label>
              <div className="radio-group">
                <label className="radio-label">
                  <input
                    type="radio"
                    name="englishAnswer2"
                    value="quickly"
                    checked={formData.englishAnswer2 === 'quickly'}
                    onChange={handleChange}
                  />
                  quickly
                </label>
                <label className="radio-label">
                  <input
                    type="radio"
                    name="englishAnswer2"
                    value="happiness"
                    checked={formData.englishAnswer2 === 'happiness'}
                    onChange={handleChange}
                  />
                  happiness (correct)
                </label>
                <label className="radio-label">
                  <input
                    type="radio"
                    name="englishAnswer2"
                    value="beautiful"
                    checked={formData.englishAnswer2 === 'beautiful'}
                    onChange={handleChange}
                  />
                  beautiful
                </label>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="englishAnswer3">Question 3: Complete the sentence: "She ___ to the store yesterday."</label>
              <input
                type="text"
                id="englishAnswer3"
                name="englishAnswer3"
                value={formData.englishAnswer3}
                onChange={handleChange}
                placeholder="Your answer"
              />
              <small className="hint">Correct answer: went</small>
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
