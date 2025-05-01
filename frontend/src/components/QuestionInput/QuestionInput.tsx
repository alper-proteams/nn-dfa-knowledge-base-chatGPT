import { useContext, useState, useEffect, useRef } from 'react'
import { FontIcon, Stack, TextField } from '@fluentui/react'
import { SendRegular } from '@fluentui/react-icons'

import Send from '../../assets/Send.svg'

import styles from './QuestionInput.module.css'
import { ChatMessage } from '../../api'
import { AppStateContext } from '../../state/AppProvider'
import { resizeImage } from '../../utils/resizeImage'

interface Props {
  onSend: (question: ChatMessage['content'], id?: string) => void
  disabled: boolean
  placeholder?: string
  clearOnSend?: boolean
  conversationId?: string
  initialQuestion?: string
}

export const QuestionInput = ({ onSend, disabled, placeholder, clearOnSend, conversationId, initialQuestion }: Props) => {
  const [question, setQuestion] = useState<string>(initialQuestion || '')
  const [base64Image, setBase64Image] = useState<string | null>(null);
  const [autoSendTimer, setAutoSendTimer] = useState<number | null>(null);
  const questionSentRef = useRef(false);

  const appStateContext = useContext(AppStateContext)
  const OYD_ENABLED = appStateContext?.state.frontendSettings?.oyd_enabled || false;
  
  // Implement typing effect for initial question
  useEffect(() => {
    console.log('[QUERY_PARAM_DEBUG] QuestionInput initialQuestion:', initialQuestion);
    if (initialQuestion && initialQuestion.trim() && !questionSentRef.current) {
      console.log('[QUERY_PARAM_DEBUG] Setting up typing effect for question:', initialQuestion);
      
      // Start with empty string and add one character at a time
      setQuestion('');
      let currentIndex = 0;
      const fullText = initialQuestion;
      
      // Function to add the next character
      const typeNextCharacter = () => {
        if (currentIndex < fullText.length) {
          setQuestion(prev => prev + fullText.charAt(currentIndex));
          currentIndex++;
          // Continue typing with a slight delay between characters (50ms)
          setAutoSendTimer(setTimeout(typeNextCharacter, 100));
        } else {
          // Typing finished, wait a moment before sending
          setAutoSendTimer(setTimeout(() => {
            console.log('[QUERY_PARAM_DEBUG] Typing effect completed, sending question:', fullText);
            if (disabled) {
              console.log('[QUERY_PARAM_DEBUG] Not sending question - disabled');
              return;
            }
            
            // Mark as sent to prevent infinite loops
            questionSentRef.current = true;
            
            const questionContent = fullText.toString();
            console.log('[QUERY_PARAM_DEBUG] Prepared question content:', questionContent);
            
            if (conversationId) {
              console.log('[QUERY_PARAM_DEBUG] Sending question with conversationId:', conversationId);
              onSend(questionContent, conversationId);
            } else {
              console.log('[QUERY_PARAM_DEBUG] Sending question without conversationId');
              onSend(questionContent);
            }
            
            if (clearOnSend) {
              setQuestion('');
            }
          }, 500)); // Short pause after typing completes before sending
        }
      };
      
      // Start the typing effect with a small initial delay
      setAutoSendTimer(setTimeout(typeNextCharacter, 300));
      
      return () => {
        if (autoSendTimer) {
          console.log('[QUERY_PARAM_DEBUG] Clearing typing effect timer');
          clearTimeout(autoSendTimer);
        }
      };
    }
  }, [initialQuestion, disabled, conversationId, onSend, clearOnSend]); // Add all dependencies

  const handleImageUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];

    if (file) {
      await convertToBase64(file);
    }
  };

  const convertToBase64 = async (file: Blob) => {
    try {
      const resizedBase64 = await resizeImage(file, 800, 800);
      setBase64Image(resizedBase64);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  const sendQuestion = () => {
    console.log('[QUERY_PARAM_DEBUG] sendQuestion called, question:', question, 'disabled:', disabled);
    if (disabled || !question.trim()) {
      console.log('[QUERY_PARAM_DEBUG] Not sending question - disabled or empty question');
      return
    }

    const questionTest: ChatMessage["content"] = base64Image ? [{ type: "text", text: question }, { type: "image_url", image_url: { url: base64Image } }] : question.toString();
    console.log('[QUERY_PARAM_DEBUG] Prepared question content:', questionTest);

    if (conversationId && questionTest !== undefined) {
      console.log('[QUERY_PARAM_DEBUG] Sending question with conversationId:', conversationId);
      onSend(questionTest, conversationId)
      setBase64Image(null)
    } else {
      console.log('[QUERY_PARAM_DEBUG] Sending question without conversationId');
      onSend(questionTest)
      setBase64Image(null)
    }

    if (clearOnSend) {
      setQuestion('')
    }
  }

  const onEnterPress = (ev: React.KeyboardEvent<Element>) => {
    if (ev.key === 'Enter' && !ev.shiftKey && !(ev.nativeEvent?.isComposing === true)) {
      ev.preventDefault()
      sendQuestion()
    }
  }

  const onQuestionChange = (_ev: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, newValue?: string) => {
    setQuestion(newValue || '')
  }

  const sendQuestionDisabled = disabled || !question.trim()

  return (
    <Stack horizontal className={styles.questionInputContainer}>
      <TextField
        className={styles.questionInputTextArea}
        placeholder={placeholder}
        multiline
        resizable={false}
        borderless
        value={question}
        onChange={onQuestionChange}
        onKeyDown={onEnterPress}
      />
      {!OYD_ENABLED && (
        <div className={styles.fileInputContainer}>
          <input
            type="file"
            id="fileInput"
            onChange={(event) => handleImageUpload(event)}
            accept="image/*"
            className={styles.fileInput}
          />
          <label htmlFor="fileInput" className={styles.fileLabel} aria-label='Upload Image'>
            <FontIcon
              className={styles.fileIcon}
              iconName={'PhotoCollection'}
              aria-label='Upload Image'
            />
          </label>
        </div>)}
      {base64Image && <img className={styles.uploadedImage} src={base64Image} alt="Uploaded Preview" />}
      <div
        className={styles.questionInputSendButtonContainer}
        role="button"
        tabIndex={0}
        aria-label="Ask question button"
        onClick={sendQuestion}
        onKeyDown={e => (e.key === 'Enter' || e.key === ' ' ? sendQuestion() : null)}>
        {sendQuestionDisabled ? (
          <SendRegular className={styles.questionInputSendButtonDisabled} />
        ) : (
          <img src={Send} className={styles.questionInputSendButton} alt="Send Button" />
        )}
      </div>
      <div className={styles.questionInputBottomBorder} />
    </Stack>
  )
}
